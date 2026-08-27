"""Schemas do Dashboard — uma requisição serve os quatro cards."""

from app.schemas.common import ApiModel, TimePoint


class ConnectionCard(ApiModel):
    connected: bool
    label: str


class MetricCard(ApiModel):
    value: float
    label: str
    unit: str | None = None
    delta_percent: float | None = None


class DashboardSummary(ApiModel):
    flight_connection: ConnectionCard
    inspection_count: MetricCard
    open_notes: MetricCard
    mape: MetricCard


class DamageSeries(ApiModel):
    """Eixo X = data da inspeção, eixo Y = avarias detectadas."""

    points: list[TimePoint]
