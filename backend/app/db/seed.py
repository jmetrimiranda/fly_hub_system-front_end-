"""Dados de demonstração para desenvolvimento.

Permite abrir o Dashboard e as três páginas com conteúdo real logo depois de
`docker compose up`, sem depender de um drone conectado.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal, engine
from app.models import Base, Damage, Dataset, DatasetImage, Inspection, ModelMetric, SapNote
from app.models.enums import CollectionStatus, InspectionStatus, NoteStatus, RoboflowStatus
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
                    )
                )

        session.add(
            ModelMetric(
                model_version="yolo-v8n-2026.07",
                metric="mape",
                value=4.72,
                measured_at=now,
                is_current=True,
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
        log.info("seed_completed", inspections=45, datasets=4)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed())
