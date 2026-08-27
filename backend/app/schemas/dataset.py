"""Schemas do domínio Dataset."""

from datetime import datetime

from app.models.enums import CollectionStatus, RoboflowStatus, SplitName
from app.schemas.common import ApiModel


class SplitDistribution(ApiModel):
    train: int = 0
    valid: int = 0
    test: int = 0
    embargo_seconds: int = 0

    @property
    def total(self) -> int:
        return self.train + self.valid + self.test


class DatasetSummary(ApiModel):
    """Uma linha da tabela em Pages > Datasets."""

    id: int
    version: str
    started_at: datetime
    duration_seconds: int
    image_count: int
    disk_bytes: int
    status: CollectionStatus
    distribution: SplitDistribution
    roboflow_status: RoboflowStatus
    roboflow_sent_at: datetime | None = None


class DatasetImageOut(ApiModel):
    """Imagem crua, sem inferência — este fluxo nunca mistura com o de inspeção."""

    id: int
    filename: str
    captured_at: datetime
    frame_number: int
    width: int | None = None
    height: int | None = None
    size_bytes: int
    split: SplitName | None = None
    embargoed: bool = False
    url: str


class DatasetDetail(DatasetSummary):
    storage_path: str
    ended_at: datetime | None = None
    roboflow_error: str | None = None


class RoboflowUploadResult(ApiModel):
    dataset_id: int
    status: RoboflowStatus
    uploaded: int = 0
    failed: int = 0
    workspace: str | None = None
    project: str | None = None
    message: str | None = None
