"""Dados de demonstração: marcar, distinguir e remover sem levar o que é real.

O risco que estes testes cobrem não é o de apagar de menos — isso alguém
percebe olhando a tela. É o de apagar **de mais**: um `--clear` que leve junto
uma coleta de voo destrói trabalho que não se refaz.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.dataset import Dataset
from app.models.enums import CollectionStatus, DataSource, InspectionStatus, NoteStatus
from app.models.inspection import Inspection, ModelMetric, SapNote
from app.services.demo_data_service import DemoDataService

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _dataset(version: str, source: DataSource, path: str = "/data/datasets/inexistente") -> Dataset:
    return Dataset(
        version=version,
        started_at=NOW,
        status=CollectionStatus.SAVED,
        storage_path=path,
        image_count=10,
        source=source,
    )


def _inspection(code: str, source: DataSource) -> Inspection:
    return Inspection(
        code=code, inspected_at=NOW, status=InspectionStatus.COMPLETED, source=source
    )


async def _populate(session) -> None:
    session.add_all(
        [
            _dataset("v0.0", DataSource.SEED),
            _dataset("v0.1", DataSource.SEED),
            _dataset("v0.7", DataSource.COLLECTED, "/data/datasets/v0.7"),
            _dataset("v0.8", DataSource.COLLECTED, "/data/datasets/v0.8"),
            _inspection("INSP-001", DataSource.SEED),
            _inspection("INSP-REAL", DataSource.COLLECTED),
            ModelMetric(
                model_version="yolo-v8n-2026.07",
                metric="mape",
                value=4.72,
                measured_at=NOW,
                source=DataSource.SEED,
            ),
            ModelMetric(
                model_version="best@abc123",
                metric="map50",
                value=0.81,
                measured_at=NOW,
                source=DataSource.COLLECTED,
            ),
        ]
    )
    await session.commit()


async def test_clear_removes_only_what_the_seed_created(session):
    """O caso que dá nome à tarefa: v0.7 e v0.8 são voo e permanecem."""
    await _populate(session)

    removed = await DemoDataService(session).clear()

    assert removed.datasets == 2
    assert removed.inspections == 1
    assert removed.model_metrics == 1

    from sqlalchemy import select

    versions = (await session.execute(select(Dataset.version).order_by(Dataset.version))).scalars()
    assert list(versions) == ["v0.7", "v0.8"]

    codes = (await session.execute(select(Inspection.code))).scalars()
    assert list(codes) == ["INSP-REAL"]

    metrics = (await session.execute(select(ModelMetric.model_version))).scalars()
    assert list(metrics) == ["best@abc123"]


async def test_clear_is_idempotent(session):
    """Clicar duas vezes no botão não é erro — a segunda não acha nada."""
    await _populate(session)
    service = DemoDataService(session)

    await service.clear()
    again = await service.clear()

    assert again.total == 0


async def test_notes_of_a_demo_inspection_do_not_survive_it(session):
    """Nota órfã apontando para inspeção que não existe mais é pior que nada."""
    inspection = _inspection("INSP-002", DataSource.SEED)
    session.add(inspection)
    await session.flush()
    # Sem a marca de propósito: é o caso de uma nota gravada por um caminho que
    # não conhece `source`, pendurada numa inspeção de demonstração.
    session.add(
        SapNote(
            inspection_id=inspection.id,
            status=NoteStatus.OPEN,
            opened_at=NOW,
            source=DataSource.COLLECTED,
        )
    )
    await session.commit()

    await DemoDataService(session).clear()

    from sqlalchemy import func, select

    assert (await session.scalar(select(func.count(SapNote.id)))) == 0


async def test_summary_counts_without_removing_anything(session):
    """O modal mostra o número antes de apagar; consultar não pode apagar."""
    await _populate(session)
    service = DemoDataService(session)

    summary = await service.summary()

    assert summary.datasets == 2
    assert summary.inspections == 1
    assert (await service.summary()).total == summary.total


async def test_the_api_removes_the_demonstration(client, session):
    await _populate(session)

    response = await client.delete("/api/v1/admin/seed")

    assert response.status_code == 200
    assert response.json()["datasets"] == 2

    listing = await client.get("/api/v1/datasets")
    assert [item["version"] for item in listing.json()["items"]] == ["v0.8", "v0.7"]


async def test_the_listing_says_which_rows_are_demonstration(client, session):
    """Sem o selo, alguém treina em cima de dado fictício sem perceber."""
    await _populate(session)

    listing = await client.get("/api/v1/datasets")
    by_version = {item["version"]: item["source"] for item in listing.json()["items"]}

    assert by_version == {
        "v0.0": "seed",
        "v0.1": "seed",
        "v0.7": "collected",
        "v0.8": "collected",
    }

    inspections = await client.get("/api/v1/inspections")
    sources = {item["code"]: item["source"] for item in inspections.json()["items"]}
    assert sources["INSP-001"] == "seed"
    assert sources["INSP-REAL"] == "collected"
