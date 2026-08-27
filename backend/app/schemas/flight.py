"""Schemas do domínio Voo: conexão, telemetria, coleta e pipeline."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CollectionStatus, PipelineStatus
from app.schemas.common import ApiModel


class FlightIndicators(ApiModel):
    """Os quatro cards do topo da página Voo."""

    availability: bool
    mediamtx_up: bool
    tunnel_up: bool
    stream_up: bool
    availability_label: str = "Sem sinal"
    mediamtx_label: str = "Fora do ar"
    tunnel_label: str = "—"
    stream_label: str = "—"


class ConnectionMetrics(ApiModel):
    """Linha da tabela CONEXÃO, no rodapé da página Voo."""

    resolution: str | None = None
    bitrate_mbps: float | None = None
    capture_fps: float | None = None
    inference_fps: float | None = None
    latency_ms: int | None = None
    dropped_frames: int = 0
    stream_uptime_seconds: int = 0
    codec: str | None = None
    model_loaded: bool = False
    model_version: str | None = None


class FlightStatus(ApiModel):
    """Estado consolidado. É a fonte de `isFlying` para o drone 3D."""

    connected: bool
    endpoint: str
    publish_url: str
    stream_path: str
    indicators: FlightIndicators
    metrics: ConnectionMetrics
    last_seen_at: datetime | None = None


class EndpointUpdate(BaseModel):
    endpoint: str = Field(min_length=3, max_length=255, examples=["rtmp://bore.pub:43516"])

    @field_validator("endpoint")
    @classmethod
    def _must_be_rtmp_or_http(cls, value: str) -> str:
        allowed = ("rtmp://", "rtmps://", "http://", "https://")
        if not value.startswith(allowed):
            raise ValueError("O endereço deve começar com rtmp://, rtmps://, http:// ou https://")
        return value.rstrip("/")


class CollectionSession(ApiModel):
    """Coleta em andamento ou recém-finalizada."""

    id: int
    version: str
    status: CollectionStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int = 0
    image_count: int = 0
    disk_bytes: int = 0
    storage_path: str


class PipelineState(ApiModel):
    status: PipelineStatus
    stream_path: str
    started_at: datetime | None = None
    model_loaded: bool = False
    model_version: str | None = None
    message: str | None = None
