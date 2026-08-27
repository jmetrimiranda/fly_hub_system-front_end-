"""Orquestra o envio de um dataset para o Roboflow.

O frontend só dispara e acompanha. Quem monta os lotes, respeita o split
temporal e lida com falha parcial é este serviço.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger
from app.integrations.roboflow.client import RoboflowClient
from app.models.dataset import DatasetImage
from app.models.enums import RoboflowStatus
from app.schemas.dataset import RoboflowUploadResult
from app.services.dataset_service import DatasetService

log = get_logger(__name__)


class RoboflowService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._datasets = DatasetService(session)

    async def upload(self, dataset_id: int) -> RoboflowUploadResult:
        dataset = await self._datasets.assert_ready_for_upload(dataset_id)
        dataset.roboflow_status = RoboflowStatus.UPLOADING
        dataset.roboflow_error = None
        await self._session.commit()
        await bus.publish("roboflow.started", dataset_id=dataset_id)

        images = (
            await self._session.execute(
                select(DatasetImage)
                .where(DatasetImage.dataset_id == dataset_id, DatasetImage.embargoed.is_(False))
                .order_by(DatasetImage.captured_at)
            )
        ).scalars().all()

        client = RoboflowClient()
        batch = f"{dataset.version}-{dataset.started_at:%Y%m%d}"
        uploaded = failed = 0

        for image in images:
            if image.split is None:
                continue
            try:
                await client.upload_image(
                    Path(dataset.storage_path) / image.relative_path,
                    split=str(image.split),
                    batch=batch,
                )
                uploaded += 1
            except Exception as exc:  # noqa: BLE001 — falha parcial não aborta o lote
                failed += 1
                log.warning("roboflow_image_failed", image=image.filename, error=str(exc))

            if (uploaded + failed) % 25 == 0:
                await bus.publish(
                    "roboflow.progress",
                    dataset_id=dataset_id,
                    uploaded=uploaded,
                    failed=failed,
                    total=len(images),
                )

        dataset.roboflow_status = (
            RoboflowStatus.SENT if failed == 0 else RoboflowStatus.FAILED
        )
        dataset.roboflow_sent_at = datetime.now(UTC)
        if failed:
            dataset.roboflow_error = f"{failed} imagem(ns) não foram enviadas."
        await self._session.commit()
        await bus.publish("roboflow.finished", dataset_id=dataset_id, uploaded=uploaded)

        return RoboflowUploadResult(
            dataset_id=dataset_id,
            status=dataset.roboflow_status,
            uploaded=uploaded,
            failed=failed,
            workspace=settings.roboflow_workspace,
            project=settings.roboflow_project,
            message=dataset.roboflow_error,
        )
