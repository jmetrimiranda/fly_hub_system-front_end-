"""Coleta de imagens: iniciar, pausar, retomar, salvar.

A máquina de estados é a mesma que o botão da página Voo mostra:

    (nada)  --start-->  RECORDING  <--pause/resume-->  PAUSED
                             |                            |
                             +----------- save -----------+
                                          |
                                          v
                                        SAVED  (particionado, aparece em Datasets)

Salvar é o único ponto em que o split temporal roda. Antes disso o dataset
existe em disco mas ainda não é versão.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import CollectionStateError
from app.core.events import bus
from app.core.logging import get_logger
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import CollectionStatus
from app.schemas.flight import CollectionSession
from app.services.splitting import SplitConfig, assign_temporal_splits

log = get_logger(__name__)

ACTIVE_STATES = (CollectionStatus.RECORDING, CollectionStatus.PAUSED)


class CollectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def current(self) -> Dataset | None:
        result = await self._session.execute(
            select(Dataset).where(Dataset.status.in_(ACTIVE_STATES)).limit(1)
        )
        return result.scalar_one_or_none()

    async def _next_version(self) -> str:
        count = await self._session.scalar(select(func.count(Dataset.id))) or 0
        return f"v{count // 10}.{count % 10}"

    async def start(self) -> CollectionSession:
        if await self.current():
            raise CollectionStateError("Já existe uma coleta em andamento.")

        now = datetime.now(UTC)
        version = await self._next_version()
        folder = settings.datasets_dir / f"collection_{now:%Y-%m-%d_%H-%M-%S}"
        for sub in ("images", "metadata"):
            Path(folder / sub).mkdir(parents=True, exist_ok=True)

        dataset = Dataset(
            version=version,
            started_at=now,
            status=CollectionStatus.RECORDING,
            storage_path=str(folder),
        )
        self._session.add(dataset)
        await self._session.commit()
        await self._session.refresh(dataset)

        await bus.publish("collection.started", dataset_id=dataset.id, version=version)
        log.info("collection_started", dataset_id=dataset.id, path=str(folder))
        return CollectionSession.model_validate(dataset)

    async def _require_active(self, expected: CollectionStatus) -> Dataset:
        dataset = await self.current()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")
        if dataset.status != expected:
            raise CollectionStateError(
                f"A coleta está em '{dataset.status}' e a ação exige '{expected}'."
            )
        return dataset

    async def pause(self) -> CollectionSession:
        dataset = await self._require_active(CollectionStatus.RECORDING)
        dataset.status = CollectionStatus.PAUSED
        await self._session.commit()
        await bus.publish("collection.paused", dataset_id=dataset.id)
        return CollectionSession.model_validate(dataset)

    async def resume(self) -> CollectionSession:
        dataset = await self._require_active(CollectionStatus.PAUSED)
        dataset.status = CollectionStatus.RECORDING
        await self._session.commit()
        await bus.publish("collection.resumed", dataset_id=dataset.id)
        return CollectionSession.model_validate(dataset)

    async def save(self) -> CollectionSession:
        """Encerra a coleta e aplica o split temporal (ADR 004)."""
        dataset = await self.current()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")

        now = datetime.now(UTC)
        dataset.ended_at = now
        dataset.duration_seconds = int((now - dataset.started_at).total_seconds())

        images = (
            await self._session.execute(
                select(DatasetImage)
                .where(DatasetImage.dataset_id == dataset.id)
                .order_by(DatasetImage.captured_at)
            )
        ).scalars().all()

        result = assign_temporal_splits(
            [image.captured_at for image in images],
            SplitConfig(
                train_ratio=settings.split_train_ratio,
                valid_ratio=settings.split_valid_ratio,
                test_ratio=settings.split_test_ratio,
                embargo_seconds=settings.split_embargo_seconds,
            ),
        )
        for image, assignment in zip(images, result.assignments, strict=True):
            image.split = assignment.split
            image.embargoed = assignment.embargoed

        dataset.train_count = result.train
        dataset.valid_count = result.valid
        dataset.test_count = result.test
        dataset.embargo_seconds = settings.split_embargo_seconds
        dataset.image_count = len(images)
        dataset.disk_bytes = sum(image.size_bytes for image in images)
        dataset.status = CollectionStatus.SAVED

        await self._session.commit()
        await bus.publish(
            "collection.saved",
            dataset_id=dataset.id,
            version=dataset.version,
            train=result.train,
            valid=result.valid,
            test=result.test,
            embargoed=result.embargoed,
        )
        log.info(
            "collection_saved",
            dataset_id=dataset.id,
            images=len(images),
            embargoed=result.embargoed,
        )
        return CollectionSession.model_validate(dataset)

    async def cancel(self) -> CollectionSession:
        dataset = await self.current()
        if dataset is None:
            raise CollectionStateError("Nenhuma coleta em andamento.")
        dataset.status = CollectionStatus.CANCELLED
        dataset.ended_at = datetime.now(UTC)
        await self._session.commit()
        await bus.publish("collection.cancelled", dataset_id=dataset.id)
        return CollectionSession.model_validate(dataset)
