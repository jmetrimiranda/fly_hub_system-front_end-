"""Galeria, exclusão, resplit, credenciais e retomada do envio ao Roboflow.

Os testes montam um dataset em disco à mão em vez de gravar um: o que está sob
teste aqui é o que acontece **depois** da coleta, e ligar o gravador só tornaria
cada caso seis segundos mais lento.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from app.core.errors import ConflictError, SecretKeyMissingError
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import CollectionStatus, RoboflowStatus, SplitName
from app.schemas.dataset import RoboflowCredentialCreate, RoboflowUploadRequest
from app.services import dataset_storage as storage
from app.services import split_runner
from app.services.dataset_service import DatasetService
from app.services.roboflow_credentials_service import RoboflowCredentialService
from app.services.roboflow_service import RoboflowService

pytestmark = pytest.mark.asyncio

FRAME_COUNT = 40


@pytest.fixture
def datasets_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "datasets_dir", tmp_path)
    return tmp_path


@pytest.fixture
def secret(monkeypatch):
    from app.core import crypto
    from app.core.config import settings

    monkeypatch.setattr(settings, "secret_key", "segredo-de-teste")
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


async def _make_dataset(session, base_dir: Path, version: str = "v0.0") -> Dataset:
    """Um dataset gravado, particionado e com as linhas no banco."""
    import cv2

    base = storage.create_version(version)
    started = datetime(2026, 8, 26, 14, 0, tzinfo=UTC)
    for index in range(1, FRAME_COUNT + 1):
        seconds = (index - 1) * 2.0
        image = np.full((48, 64, 3), index * 5 % 255, dtype=np.uint8)
        ok, buffer = cv2.imencode(".jpg", image)
        assert ok
        (base / storage.RAW_DIR / f"{index:06d}_t{seconds:.2f}.jpg").write_bytes(buffer.tobytes())

    manifest = split_runner.run(base)

    dataset = Dataset(
        version=version,
        started_at=started,
        ended_at=started + timedelta(seconds=FRAME_COUNT * 2),
        status=CollectionStatus.SAVED,
        storage_path=str(base),
        image_count=FRAME_COUNT,
        train_count=manifest["counts"]["train"],
        valid_count=manifest["counts"]["valid"],
        test_count=manifest["counts"]["test"],
        embargoed_count=manifest["counts"]["embargoed"],
    )
    session.add(dataset)
    await session.flush()

    assigned: dict[str, str | None] = {}
    for split in storage.SPLITS:
        for entry in manifest["files"][split]:
            assigned[entry["file"]] = split
    for entry in manifest["files"]["embargoed"]:
        assigned[entry["file"]] = None

    for index in range(1, FRAME_COUNT + 1):
        seconds = (index - 1) * 2.0
        name = f"{index:06d}_t{seconds:.2f}.jpg"
        split = assigned.get(name)
        session.add(
            DatasetImage(
                dataset_id=dataset.id,
                filename=name,
                relative_path=f"{split}/images/{name}" if split else f"raw/{name}",
                captured_at=started + timedelta(seconds=seconds),
                frame_number=index,
                width=64,
                height=48,
                size_bytes=(base / storage.RAW_DIR / name).stat().st_size,
                split=SplitName(split) if split else None,
                embargoed=split is None,
            )
        )
    await session.commit()
    return dataset


# --- galeria -----------------------------------------------------------------


async def test_the_gallery_filters_by_partition(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)

    page = await service.images(dataset.id, split=SplitName.VALID)
    assert page.total == dataset.valid_count
    assert all(item.split == SplitName.VALID for item in page.items)


async def test_every_image_offers_a_thumbnail_and_a_full_size_url(session, datasets_dir):
    """A grade nunca baixa o JPEG inteiro: 500 deles travam a aba."""
    dataset = await _make_dataset(session, datasets_dir)
    page = await DatasetService(session).images(dataset.id, split=SplitName.TRAIN)

    item = page.items[0]
    assert item.thumb_url.endswith("/thumb")
    assert item.url.endswith("/raw")
    assert item.thumb_url != item.url


async def test_the_thumbnail_is_smaller_than_the_original(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)
    page = await service.images(dataset.id, split=SplitName.TRAIN)
    image_id = page.items[0].id

    thumb = await service.image_file(dataset.id, image_id, thumb=True)
    full = await service.image_file(dataset.id, image_id, thumb=False)
    assert thumb != full
    assert thumb.parent.parent.name == storage.THUMBS_DIR


# --- exclusão ----------------------------------------------------------------


async def test_deleting_an_image_removes_it_from_the_partition_and_from_raw(
    session, datasets_dir
):
    """Só da partição faria o resplit ressuscitar tudo que foi excluído."""
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)
    base = Path(dataset.storage_path)

    page = await service.images(dataset.id, split=SplitName.TRAIN)
    target = page.items[0]
    result = await service.delete_images(dataset.id, [target.id])

    assert result.removed == 1
    assert not (base / "train" / "images" / target.filename).exists()
    assert not (base / storage.RAW_DIR / target.filename).exists()


async def test_counts_update_and_the_drift_is_reported_after_deleting(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)
    before = dataset.train_count

    page = await service.images(dataset.id, split=SplitName.TRAIN)
    await service.delete_images(dataset.id, [item.id for item in page.items[:3]])

    detail = await service.detail(dataset.id)
    assert detail.distribution.train == before - 3
    assert detail.counts.train == before - 3
    assert detail.drifted is True  # o manifesto não foi reescrito, e isso aparece


async def test_resplit_rebuilds_the_partitions_from_raw(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)

    page = await service.images(dataset.id, split=SplitName.TRAIN)
    await service.delete_images(dataset.id, [item.id for item in page.items[:5]])
    result = await service.resplit(dataset.id)

    detail = await service.detail(dataset.id)
    assert detail.drifted is False  # as proporções voltam a valer
    assert result.counts.total == result.distribution.total
    assert result.counts.raw == FRAME_COUNT - 5


async def test_deleting_the_whole_dataset_requires_typing_the_version(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    service = DatasetService(session)

    with pytest.raises(ConflictError, match="v0.0"):
        await service.delete_dataset(dataset.id, "v0")
    assert Path(dataset.storage_path).is_dir()

    await service.delete_dataset(dataset.id, "v0.0")
    assert not Path(dataset.storage_path).exists()


# --- credenciais --------------------------------------------------------------


async def test_a_saved_credential_is_never_readable_in_clear_text(session, datasets_dir, secret):
    """Nenhum endpoint devolve a chave — nem inteira, nem mascarada."""
    service = RoboflowCredentialService(session)
    await service.create(
        RoboflowCredentialCreate(
            label="Equipe", workspace="acme", project="postes", api_key="chave-supersecreta"
        )
    )

    listed = await service.list()
    assert [item.label for item in listed] == ["Equipe"]
    serialized = str([item.model_dump() for item in listed])
    assert "chave-supersecreta" not in serialized
    assert not any("key" in field for item in listed for field in item.model_dump())


async def test_the_key_is_not_stored_in_clear_text_in_the_database(session, datasets_dir, secret):
    from app.models.dataset import RoboflowCredential

    service = RoboflowCredentialService(session)
    created = await service.create(
        RoboflowCredentialCreate(
            label="Equipe", workspace="acme", project="postes", api_key="chave-supersecreta"
        )
    )

    row = await session.get(RoboflowCredential, created.id)
    assert row is not None
    assert "chave-supersecreta" not in row.api_key_encrypted

    target = await service.target(created.id)
    assert target.api_key == "chave-supersecreta"  # só decifrada para uso imediato
    assert "chave-supersecreta" not in repr(target)


async def test_without_a_secret_key_nothing_is_saved(session, datasets_dir, monkeypatch):
    from app.core import crypto
    from app.core.config import settings

    monkeypatch.setattr(settings, "secret_key", "")
    crypto._fernet.cache_clear()

    with pytest.raises(SecretKeyMissingError, match="SECRET_KEY"):
        await RoboflowCredentialService(session).create(
            RoboflowCredentialCreate(
                label="Equipe", workspace="acme", project="postes", api_key="chave-supersecreta"
            )
        )


# --- envio --------------------------------------------------------------------


async def test_a_partial_upload_resumes_where_it_stopped(session, datasets_dir):
    """300 de 500 enviadas: o próximo envio começa da 301, não do começo."""
    dataset = await _make_dataset(session, datasets_dir)
    service = RoboflowService(session)

    pending_before = await service._pending(dataset.id)
    assert pending_before

    already = pending_before[:3]
    for image in already:
        image.roboflow_sent_at = datetime.now(UTC)
    await session.commit()

    pending_after = await service._pending(dataset.id)
    assert len(pending_after) == len(pending_before) - 3
    assert not {image.id for image in already} & {image.id for image in pending_after}


async def test_embargoed_frames_are_never_uploaded(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    pending = await RoboflowService(session)._pending(dataset.id)

    assert all(image.embargoed is False for image in pending)
    assert all(image.split is not None for image in pending)


async def test_uploading_an_unsaved_dataset_is_refused(session, datasets_dir):
    dataset = await _make_dataset(session, datasets_dir)
    dataset.status = CollectionStatus.RECORDING
    await session.commit()

    with pytest.raises(ConflictError, match="Salve a coleta"):
        await RoboflowService(session).start(dataset.id, RoboflowUploadRequest())


async def test_editing_a_dataset_while_it_uploads_is_refused(session, datasets_dir):
    """Resplit no meio de um envio faria o uploader procurar caminhos extintos."""
    dataset = await _make_dataset(session, datasets_dir)
    dataset.roboflow_status = RoboflowStatus.UPLOADING
    await session.commit()

    with pytest.raises(ConflictError, match="em andamento"):
        await DatasetService(session).resplit(dataset.id)

