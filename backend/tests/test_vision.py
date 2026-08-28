"""Leitor de quadros e detector — sem rede e sem pesos.

Os três comportamentos testados aqui são os que o M4TD mediu e que a migração
não pode perder: latência que não acumula, aplicação que sobe sem modelo, e
backoff que não vira martelo em cima do RTSP.
"""

import asyncio
import threading
import time

import numpy as np
import pytest

from app.integrations.vision.detector import Detector
from app.integrations.vision.metrics import RateMeter
from app.integrations.vision.reader import (
    RECONNECT_MAX_S,
    RECONNECT_MIN_S,
    Consumers,
    FrameSlot,
    RtspReader,
    next_backoff,
)


def frame(width: int = 8, height: int = 6) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


class FakeCapture:
    """`VideoCapture` de mentira: abre, entrega o que mandarem e conta releases."""

    def __init__(self, frames: list, opened: bool = True) -> None:
        self._frames = list(frames)
        self._opened = opened
        self.released = 0

    def isOpened(self) -> bool:  # noqa: N802 — assinatura do OpenCV
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self) -> None:
        self.released += 1

    def set(self, *_args) -> None:
        return None


# --- slot de um quadro -------------------------------------------------------


def test_quadro_antigo_e_descartado_quando_chega_um_novo():
    """A latência não acumula: quem consome sempre pega o mais recente."""
    slot = FrameSlot()

    slot.publish("primeiro")
    slot.publish("segundo")
    slot.publish("terceiro")

    item = slot.take(last_seq=0, timeout=0.1)
    assert item is not None
    latest, _ = item
    assert latest == "terceiro"
    # Dois quadros foram sobrescritos sem ninguém consumir.
    assert slot.dropped == 2


def test_slot_devolve_none_no_timeout_sem_quadro_novo():
    slot = FrameSlot()
    slot.publish("único")
    _, seq = slot.take(last_seq=0, timeout=0.1)

    assert slot.take(last_seq=seq, timeout=0.05) is None


def test_consumidor_desconhecido_nao_entra_no_registro():
    consumers = Consumers()
    token = consumers.add("mjpeg")

    assert consumers.counts() == {"mjpeg": 1, "collect": 0, "total": 1}
    with pytest.raises(ValueError, match="consumidor desconhecido"):
        consumers.add("websocket")

    consumers.discard(token)
    assert consumers.total() == 0


# --- backoff -----------------------------------------------------------------


def test_backoff_cresce_e_satura_em_dez_segundos():
    delays = []
    current = RECONNECT_MIN_S
    for _ in range(7):
        delays.append(current)
        current = next_backoff(current)

    assert delays[:5] == [1.0, 2.0, 4.0, 8.0, 10.0]
    assert max(delays) == RECONNECT_MAX_S


def test_conexao_que_abre_e_nao_entrega_quadro_nao_reinicia_o_backoff():
    """O contrário — zerar ao abrir — dava uma abertura de RTSP por segundo.

    Um path que abre e nunca entrega quadro é o publicador que caiu sem o
    MediaMTX derrubar o path. Zerar o backoff no `isOpened()` fazia o leitor
    gastar um FFmpeg inteiro por segundo, para sempre.
    """
    waits: list[float] = []
    reader = None

    def waiter(seconds: float) -> bool:
        waits.append(seconds)
        if len(waits) >= 5:
            reader.stop()  # encerra o laço depois de cinco esperas
        return False

    reader = RtspReader(
        url=lambda: "rtsp://exemplo/live",
        open_capture=lambda _url: FakeCapture(frames=[]),  # abre, não lê nada
        path_ready=lambda: True,
        waiter=waiter,
    )
    reader.consumers.add("mjpeg")
    reader.run()

    assert waits == [1.0, 2.0, 4.0, 8.0, 10.0]


def test_leitor_nao_abre_rtsp_quando_o_broker_diz_que_nao_ha_path():
    aberturas = []
    reader = None

    def waiter(seconds: float) -> bool:
        reader.stop()
        return False

    def open_capture(url: str):
        aberturas.append(url)
        return FakeCapture(frames=[frame()])

    reader = RtspReader(
        url=lambda: "rtsp://exemplo/live",
        open_capture=open_capture,
        path_ready=lambda: False,
        waiter=waiter,
    )
    reader.consumers.add("mjpeg")
    reader.run()

    assert aberturas == []
    assert reader.snapshot().error == "nenhum path publicando no MediaMTX"


# --- leitura -----------------------------------------------------------------


def test_leitor_publica_cada_quadro_lido():
    published = []
    reader = None

    def waiter(_seconds: float) -> bool:
        reader.stop()
        return False

    reader = RtspReader(
        url=lambda: "rtsp://exemplo/live",
        open_capture=lambda _url: FakeCapture(frames=[frame(), frame()]),
        path_ready=lambda: True,
        waiter=waiter,
    )
    # O slot é limpo na desconexão — que é o que acontece quando o `FakeCapture`
    # fica sem quadros. Gravar na publicação é o que sobrevive a isso.
    original = reader.slot.publish
    reader.slot.publish = lambda item: (published.append(item), original(item))[1]
    reader.consumers.add("mjpeg")
    reader.run()

    assert [item.seq for item in published] == [1, 2]
    assert published[0].size == (8, 6)
    assert published[0].elapsed >= 0
    assert reader.snapshot().frames == 2


def test_mudanca_de_resolucao_vira_aviso():
    """Qualidade "Automático" no FlightHub troca o perfil no meio do voo."""
    reader = None

    def waiter(_seconds: float) -> bool:
        reader.stop()
        return False

    reader = RtspReader(
        url=lambda: "rtsp://exemplo/live",
        open_capture=lambda _url: FakeCapture(frames=[frame(1280, 720), frame(640, 480)]),
        path_ready=lambda: True,
        waiter=waiter,
    )
    reader.consumers.add("mjpeg")
    reader.run()

    change = reader.snapshot().resolution_change
    assert change is not None
    assert (change.previous, change.current) == ("1280×720", "640×480")


def test_sem_consumidor_o_leitor_nao_toca_no_rtsp():
    aberturas = []
    reader = None

    def waiter(_seconds: float) -> bool:
        reader.stop()
        return False

    def open_capture(url: str):
        aberturas.append(url)
        return FakeCapture(frames=[frame()])

    reader = RtspReader(
        url=lambda: "rtsp://exemplo/live",
        open_capture=open_capture,
        path_ready=lambda: True,
        waiter=waiter,
    )
    reader.run()  # ninguém registrado

    assert aberturas == []


# --- detector ----------------------------------------------------------------


def test_detector_sem_pesos_devolve_o_quadro_intacto(tmp_path):
    """Estado inicial do projeto: não há modelo, e isso não é erro."""
    detector = Detector(weights=tmp_path / "nao-existe.pt")
    image = frame()

    output, detections = detector.detect(image)

    assert output is image
    assert detections == []
    assert detector.is_loaded is False
    status = detector.status()
    assert status["error"] is None
    assert status["mode"] == "passthrough"
    assert status["weights_exists"] is False


def test_detector_com_pesos_invalidos_registra_o_erro_e_segue_em_passthrough(tmp_path):
    """Terceiro estado: havia arquivo, mas a carga falhou. O vídeo não para."""
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"isto nao e um modelo")

    detector = Detector(weights=weights)
    image = frame()
    output, detections = detector.detect(image)

    assert output is image
    assert detections == []
    assert detector.is_loaded is False
    status = detector.status()
    assert status["weights_exists"] is True
    assert status["error"]  # ou ultralytics ausente, ou pesos ilegíveis
    assert status["mode"] == "passthrough"


def test_detector_percebe_o_arquivo_aparecendo(tmp_path, monkeypatch):
    """O operador copia o best.pt para a pasta com a aplicação no ar."""
    weights = tmp_path / "best.pt"
    detector = Detector(weights=weights)
    assert detector.poll()["weights_exists"] is False

    weights.write_bytes(b"pesos")
    # A checagem é no máximo uma por segundo; sem isto o poll não releria.
    monkeypatch.setattr(detector, "_checked_at", time.monotonic() - 2)

    assert detector.poll()["weights_exists"] is True


# --- medição -----------------------------------------------------------------


def test_taxa_usa_janela_deslizante_e_zera_sem_eventos():
    meter = RateMeter(window=0.2)
    for _ in range(5):
        meter.tick()
        time.sleep(0.01)

    assert meter.value() > 0
    time.sleep(0.25)
    assert meter.value() == 0.0


def test_slot_acorda_quem_espera_quando_o_quadro_chega():
    slot = FrameSlot()
    received: list[str] = []

    def consume() -> None:
        item = slot.take(last_seq=0, timeout=1.0)
        if item:
            received.append(item[0])

    thread = threading.Thread(target=consume)
    thread.start()
    time.sleep(0.05)
    slot.publish("quadro")
    thread.join(timeout=1)

    assert received == ["quadro"]


# --- saída MJPEG -------------------------------------------------------------


async def test_mjpeg_emite_quadro_sintetico_quando_nao_ha_sinal():
    """Sem stream o gerador não encerra: manda o motivo desenhado, a ~1 fps.

    Encerrar o multipart deixaria um ícone quebrado na tela e obrigaria o
    navegador a reconectar; assim a imagem volta sozinha na mesma conexão.
    """
    from app.integrations.vision.stream import VideoStream

    stream = VideoStream()
    frames = stream.mjpeg()
    try:
        part = await asyncio.wait_for(anext(frames), timeout=10)
    finally:
        await frames.aclose()

    assert part.startswith(b"--frame")
    assert b"Content-Type: image/jpeg" in part
    # O consumidor sai do registro ao fechar: o RTSP não fica aberto à toa.
    assert stream.consumers.total() == 0
