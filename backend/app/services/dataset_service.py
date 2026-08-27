"""Consulta e envio de datasets."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.dataset import Dataset, DatasetImage
from app.models.enums import CollectionStatus, RoboflowStatus
from app.schemas.common import Page
from app.schemas.dataset import (
    DatasetDetail,
    DatasetImageOut,
    DatasetSummary,
    SplitDistribution,
)

log = get_logger(__name__)


def _to_summary(dataset: Dataset) -> DatasetSummary:
    return DatasetSummary(
        id=dataset.id,
        version=dataset.version,
        started_at=dataset.started_at,
        duration_seconds=dataset.duration_seconds,
        image_count=dataset.image_count,
        disk_bytes=dataset.disk_bytes,
        status=dataset.status,
        distribution=SplitDistribution(
            train=dataset.train_count,
            valid=dataset.valid_count,
            test=dataset.test_count,
            embargo_seconds=dataset.embargo_seconds,
        ),
        roboflow_status=dataset.roboflow_status,
        roboflow_sent_at=dataset.roboflow_sent_at,
    )


class DatasetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, page: int = 1, page_size: int = 50) -> Page[DatasetSummary]:
        total = await self._session.scalar(select(func.count(Dataset.id))) or 0
        rows = (
            await self._session.execute(
                select(Dataset)
                .order_by(Dataset.started_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return Page(
            items=[_to_summary(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get(self, dataset_id: int) -> Dataset:
        dataset = await self._session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} não encontrado.")
        return dataset

    async def detail(self, dataset_id: int) -> DatasetDetail:
        dataset = await self.get(dataset_id)
        return DatasetDetail(
            **_to_summary(dataset).model_dump(),
            storage_path=dataset.storage_path,
            ended_at=dataset.ended_at,
            roboflow_error=dataset.roboflow_error,
        )

    async def images(
        self, dataset_id: int, page: int = 1, page_size: int = 60
    ) -> Page[DatasetImageOut]:
        """Imagens **cruas**. A página Datasets nunca mostra saída do modelo."""
        await self.get(dataset_id)
        total = (
            await self._session.scalar(
                select(func.count(DatasetImage.id)).where(DatasetImage.dataset_id == dataset_id)
            )
            or 0
        )
        rows = (
            await self._session.execute(
                select(DatasetImage)
                .where(DatasetImage.dataset_id == dataset_id)
                .order_by(DatasetImage.captured_at)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return Page(
            items=[
                DatasetImageOut(
                    **{
                        key: getattr(row, key)
                        for key in (
                            "id",
                            "filename",
                            "captured_at",
                            "frame_number",
                            "width",
                            "height",
                            "size_bytes",
                            "split",
                            "embargoed",
                        )
                    },
                    url=f"/api/v1/datasets/{dataset_id}/images/{row.id}/raw",
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def assert_ready_for_upload(self, dataset_id: int) -> Dataset:
        dataset = await self.get(dataset_id)
        if dataset.status != CollectionStatus.SAVED:
            raise ConflictError("Salve a coleta antes de enviar para o Roboflow.")
        if dataset.roboflow_status in (RoboflowStatus.QUEUED, RoboflowStatus.UPLOADING):
            raise ConflictError("Este dataset já está sendo enviado.")
        return dataset
