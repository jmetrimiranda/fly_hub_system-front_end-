"""Dados de demonstração para desenvolvimento.

Permite abrir o Dashboard e as três páginas com conteúdo logo depois de
`docker compose up`, sem depender de um drone conectado.

Tudo que sai daqui é gravado com `source="seed"`. É essa marca — e não a data,
o id ou o formato do código — que permite remover a demonstração depois sem
tocar em voo de verdade:

    python -m app.db.seed            popula
    python -m app.db.seed --clear    remove só o que o seed criou

A regra do `--clear` mora em `services/demo_data_service.py`, compartilhada com
o `DELETE /api/v1/admin/seed` que a tela Datasets aciona.
"""

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal, engine
from app.models import Base, Damage, Dataset, DatasetImage, Inspection, ModelMetric, SapNote
from app.models.enums import (
    CollectionStatus,
    DataSource,
    InspectionStatus,
    NoteStatus,
    RoboflowStatus,
)
from app.services.demo_data_service import DemoDataService
from app.services.splitting import SplitConfig, assign_temporal_splits

log = get_logger(__name__)
LABELS = ["corrosão", "trinca", "isolador partido", "vegetação", "conector solto"]


async def seed() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        now = datetime.now(UTC)
        random.seed(42)

        for index in range(45):
            at = now - timedelta(days=44 - index, hours=random.randint(8, 16))
            damage_count = max(0, int(random.gauss(3, 2)))
            inspection = Inspection(
                code=f"INSP-{index + 1:03d}",
                inspected_at=at,
                flight_time_seconds=random.randint(9, 26) * 60,
                damage_count=damage_count,
                status=InspectionStatus.COMPLETED,
                model_version="yolo-v8n-2026.07",
                asset_tag=f"LT-{random.randint(100, 180)}",
                source=DataSource.SEED,
            )
            session.add(inspection)
            await session.flush()

            for _ in range(damage_count):
                session.add(
                    Damage(
                        inspection_id=inspection.id,
                        label=random.choice(LABELS),
                        confidence=round(random.uniform(0.62, 0.98), 3),
                        detected_at=at + timedelta(seconds=random.randint(0, 900)),
                    )
                )

            if damage_count >= 3 and random.random() < 0.6:
                session.add(
                    SapNote(
                        inspection_id=inspection.id,
                        sap_number=f"{random.randint(400000, 499999)}",
                        status=NoteStatus.OPEN if random.random() < 0.7 else NoteStatus.CLOSED,
                        opened_at=at + timedelta(hours=2),
                        description="Avaria detectada em inspeção automatizada.",
                        source=DataSource.SEED,
                    )
                )

        session.add(
            ModelMetric(
                model_version="yolo-v8n-2026.07",
                metric="mape",
                value=4.72,
                measured_at=now,
                is_current=True,
                source=DataSource.SEED,
            )
        )

        for index in range(4):
            started = now - timedelta(days=12 - index * 3)
            count = random.randint(180, 900)
            dataset = Dataset(
                version=f"v0.{index}",
                started_at=started,
                ended_at=started + timedelta(seconds=count // 30),
                duration_seconds=count // 30,
                image_count=count,
                disk_bytes=count * 105_000,
                status=CollectionStatus.SAVED,
                storage_path=f"/data/datasets/collection_{started:%Y-%m-%d_%H-%M-%S}",
                roboflow_status=RoboflowStatus.SENT if index < 2 else RoboflowStatus.NEVER_SENT,
                roboflow_sent_at=now if index < 2 else None,
                source=DataSource.SEED,
            )
            session.add(dataset)
            await session.flush()

            stamps = [started + timedelta(milliseconds=33 * frame) for frame in range(count)]
            result = assign_temporal_splits(stamps, SplitConfig())
            for frame, (at, assignment) in enumerate(zip(stamps, result.assignments, strict=True)):
                session.add(
                    DatasetImage(
                        dataset_id=dataset.id,
                        filename=f"frame_{frame:06d}.jpg",
                        relative_path=f"images/frame_{frame:06d}.jpg",
                        captured_at=at,
                        frame_number=frame,
                        width=960,
                        height=720,
                        size_bytes=105_000,
                        split=assignment.split,
                        embargoed=assignment.embargoed,
                    )
                )
            dataset.train_count = result.train
            dataset.valid_count = result.valid
            dataset.test_count = result.test
            dataset.embargo_seconds = SplitConfig().embargo_seconds

        await session.commit()
        # Em nível de aviso de propósito: quem sobe o ambiente precisa ler, no
        # meio do log do post-create, que o que está na tela não é voo.
        log.warning(
            "seed_completed",
            inspections=45,
            datasets=4,
            source=str(DataSource.SEED),
            aviso=(
                "Estes são dados de DEMONSTRAÇÃO, não coletas reais. "
                "Remova com: python -m app.db.seed --clear"
            ),
        )


async def clear() -> None:
    """Remove o que o seed criou. Coleta real não é tocada."""
    async with SessionLocal() as session:
        removed = await DemoDataService(session).clear()
    log.info(
        "seed_cleared",
        datasets=removed.datasets,
        inspections=removed.inspections,
        model_metrics=removed.model_metrics,
        sap_notes=removed.sap_notes,
    )
    print(
        f"Removidos: {removed.datasets} dataset(s), {removed.inspections} inspeção(ões), "
        f"{removed.sap_notes} nota(s) SAP e {removed.model_metrics} métrica(s) de demonstração.\n"
        "Datasets e inspeções coletados de verdade permanecem."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dados de demonstração da plataforma.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="remove os dados de demonstração em vez de criá-los",
    )
    args = parser.parse_args()
    configure_logging()
    asyncio.run(clear() if args.clear else seed())


if __name__ == "__main__":
    main()
