"""Coleta: guarda, máquina de estados, deduplicação e split em disco.

Nada aqui abre RTSP. O gravador lê o quadro de `video.raw_frame()`, e o teste
troca essa função por um gerador de imagens — é o que permite exercitar
pausar/continuar e dedup sem drone, sem MediaMTX e sem FFmpeg.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.core.errors import PreflightError
from app.integrations.flyhub.client import FlightProbe, StreamSnapshot
from app.integrations.vision.reader import Frame
from app.models.enums import CollectionStatus
from app.schemas.flight import CollectionStart
from app.services import dataset_storage as storage
from app.services import split_runner
from app.services.collection_runtime import recorder
from app.services.collection_service import CollectionService

pytestmark = pytest.mark.asyncio


class _FakeClient:
    """FlyHub de mentira: os indicadores que a guarda consulta, nada mais."""

    def __init__(self, *, broker_up: bool = True, stream_ready: bool = True) -> None:
        self._probe = FlightProbe(broker_up=broker_up, stream=StreamSnapshot(ready=stream_ready))

    async def probe(self, _path: str | None = None) -> FlightProbe:
        return self._probe

    async def tunnel_up(self) -> bool:
        return False


class _FrameSource:
    """Produz quadros como o leitor produziria, com controle sobre o conteúdo."""

    def __init__(self) -> None:
        self.seq = 0
        self.value = 0

    def __call__(self) -> Frame:
        self.seq += 1
        now = time.monotonic()
        image = np.full((48, 64, 3), self.value, dtype=np.uint8)
        return Frame(
            image=image,
            seq=self.seq,
            captured_at=now,
            captured_epoch=time.time(),
            session_started_at=now,
        )


@pytest.fixture
def datasets_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "datasets_dir", tmp_path)
    return tmp_path


@pytest.fixture
def frames(monkeypatch):
    source = _FrameSource()
    from app.integrations.vision import video

    monkeypatch.setattr(video, "raw_frame", source)
    monkeypatch.setattr(video, "start", lambda: None)
    return source


# --- guarda -------------------------------------------------------------------


async def test_preflight_blocks_when_the_stream_is_down(session, datasets_dir):
    service = CollectionService(session, client=_FakeClient(stream_ready=False))
    check = await service.preflight()

    assert check.ok is False
    stream = next(item for item in check.checks if item.key == "stream")
    assert stream.ok is False
    assert stream.fix  # o modal precisa dizer o que fazer, não só que falhou
    assert [item.key for item in check.failed] == ["stream"]


async def test_starting_with_a_red_stream_is_refused_by_the_server(session, datasets_dir):
    """A guarda do cliente não é a guarda. O servidor revalida."""
    service = CollectionService(session, client=_FakeClient(stream_ready=False))

    with pytest.raises(PreflightError) as excinfo:
        await service.start(CollectionStart())

    assert excinfo.value.details["failed"][0]["key"] == "stream"
    assert not list(datasets_dir.iterdir())  # nada criado em disco


async def test_the_tunnel_never_blocks_the_collection(session, datasets_dir):
    """O túnel é informativo: por onde o drone chegou não muda a gravação."""
    service = CollectionService(session, client=_FakeClient())
    check = await service.preflight()

    tunnel = next(item for item in check.checks if item.key == "tunnel")
    assert tunnel.blocking is False
    assert check.ok is True


# --- máquina de estados -------------------------------------------------------


async def test_pause_stops_writing_and_resume_continues_the_same_session(
    session, datasets_dir, frames
):
    service = CollectionService(session, client=_FakeClient())
    started = await service.start(
        CollectionStart(interval_seconds=0.5, frame_limit=None, dedup=False)
    )
    raw = datasets_dir / started.version / storage.RAW_DIR

    try:
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) >= 2)
        await service.pause()
        during_pause = len(list(raw.glob("*.jpg")))

        time.sleep(1.5)  # tempo para vários intervalos de amostragem passarem
        assert len(list(raw.glob("*.jpg"))) == during_pause

        await service.resume()
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) > during_pause)

        current = await service.current()
        assert current is not None
        assert current.version == started.version  # a mesma sessão, não outra
        assert current.status == CollectionStatus.RECORDING
    finally:
        recorder.abort()


async def test_dedup_drops_the_identical_frame_and_keeps_the_different_one(
    session, datasets_dir, frames
):
    service = CollectionService(session, client=_FakeClient())
    started = await service.start(
        CollectionStart(interval_seconds=0.5, frame_limit=None, dedup=True)
    )
    raw = datasets_dir / started.version / storage.RAW_DIR

    try:
        # O gerador devolve sempre a mesma cor: só o primeiro quadro é salvo.
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) >= 1)
        time.sleep(1.5)
        assert len(list(raw.glob("*.jpg"))) == 1
        assert recorder.status().dedup_skipped > 0

        # Cena diferente: volta a salvar.
        frames.value = 200
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) >= 2)
    finally:
        recorder.abort()


async def test_the_frame_name_carries_index_and_relative_time(session, datasets_dir, frames):
    service = CollectionService(session, client=_FakeClient())
    started = await service.start(
        CollectionStart(interval_seconds=0.5, frame_limit=None, dedup=False)
    )
    raw = datasets_dir / started.version / storage.RAW_DIR
    try:
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) >= 1)
        name = sorted(path.name for path in raw.glob("*.jpg"))[0]
        assert storage.parse_frame_name(name) == (1, 0.0)
    finally:
        recorder.abort()


async def test_saving_partitions_the_folder_and_writes_the_manifest(
    session, datasets_dir, frames
):
    service = CollectionService(session, client=_FakeClient())
    started = await service.start(
        CollectionStart(interval_seconds=0.5, frame_limit=None, dedup=False)
    )
    base = datasets_dir / started.version
    raw = base / storage.RAW_DIR

    # Doze quadros é o mínimo que o split aceita particionar (`min_frames`).
    _wait_until(lambda: len(list(raw.glob("*.jpg"))) >= 12, timeout=25)
    saved = await service.save()

    assert saved.status == CollectionStatus.SAVED
    for name in storage.SPLITS:
        assert (base / name / "images").is_dir()
    assert (base / storage.RAW_DIR).is_dir()  # mantido: permite refazer o split
    assert (base / storage.SESSION_NAME).is_file()

    manifest = split_runner.read_manifest(base)
    assert manifest is not None
    assert manifest["strategy"] == "temporal_contiguous"
    assert manifest["counts"]["kept"] + manifest["counts"]["embargoed"] == manifest["total_raw"]
    assert manifest["embargo"]["seconds"] >= 0


def _wait_until(condition, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("condição não foi satisfeita dentro do tempo")


async def test_the_automatic_pause_reaches_the_database_row(session, datasets_dir, frames):
    """A auto-pausa acontece na thread do gravador, que não escreve no banco.

    Sem a reconciliação, `Continuar` batia num 409 dizendo que a coleta estava
    "em recording e a ação exige paused" — com a tela mostrando PAUSADO ao lado.
    """
    service = CollectionService(session, client=_FakeClient())
    await service.start(CollectionStart(interval_seconds=0.5, frame_limit=2, dedup=False))

    try:
        _wait_until(lambda: recorder.status().status == CollectionStatus.PAUSED)

        current = await service.current()
        assert current is not None
        assert current.status == CollectionStatus.PAUSED
        assert current.progress is not None
        assert "limite" in (current.progress.paused_reason or "")

        # E a transição seguinte funciona, em vez de conflitar.
        resumed = await service.resume()
        assert resumed.status == CollectionStatus.RECORDING
    finally:
        recorder.abort()


async def test_resuming_past_the_limit_keeps_recording(session, datasets_dir, frames):
    """Clicar em Continuar depois do limite é decisão de ignorá-lo.

    Mantendo o limite, a amostradora gravaria um quadro e pausaria de novo a
    cada clique, e a tela pareceria travada sem nada errado acontecendo.
    """
    service = CollectionService(session, client=_FakeClient())
    started = await service.start(
        CollectionStart(interval_seconds=0.5, frame_limit=2, dedup=False)
    )
    raw = datasets_dir / started.version / storage.RAW_DIR

    try:
        _wait_until(lambda: recorder.status().status == CollectionStatus.PAUSED)
        await service.resume()
        _wait_until(lambda: len(list(raw.glob("*.jpg"))) > 3)
        assert recorder.status().status == CollectionStatus.RECORDING
    finally:
        recorder.abort()
