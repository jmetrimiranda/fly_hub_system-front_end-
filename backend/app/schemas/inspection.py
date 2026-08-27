"""Schemas do domínio Inspeção."""

from datetime import datetime

from app.models.enums import InspectionStatus
from app.schemas.common import ApiModel


class DamageOut(ApiModel):
    id: int
    label: str
    confidence: float
    detected_at: datetime
    frame_reference: str | None = None


class InspectionSummary(ApiModel):
    """Linha das tabelas do Dashboard e de Aplicação > Inspeção."""

    id: int
    code: str
    inspected_at: datetime
    flight_time_seconds: int
    damage_count: int
    open_note_count: int = 0
    status: InspectionStatus


class InspectionDetail(InspectionSummary):
    model_version: str | None = None
    asset_tag: str | None = None
    damages: list[DamageOut] = []


class InspectionStatistics(ApiModel):
    """Alimenta o gráfico de percentual em Aplicação > Inspeção."""

    total: int
    with_damage: int
    without_damage: int
    damage_ratio: float
    average_damage_per_inspection: float
    period_start: datetime | None = None
    period_end: datetime | None = None
