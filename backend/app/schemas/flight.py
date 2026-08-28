"""Schemas do domínio Voo: conexão, telemetria, coleta e pipeline."""

from datetime import datetime
from typing import Literal

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


class ResolutionChange(ApiModel):
    """Aviso de troca de resolução no meio da transmissão.

    Acontece com a qualidade do canal em "Automático" no FlightHub e é a causa
    mais comum de queda da captura. Não é dispensável pela interface: enquanto
    a resolução oscila o problema segue ativo, e um dataset coletado nesse
    intervalo sai com resoluções misturadas. O servidor deixa de mandá-lo
    depois de cinco minutos sem nova troca.
    """

    previous: str
    current: str
    at: datetime


class ConnectionMetrics(ApiModel):
    """Linha da tabela CONEXÃO, no rodapé da página Voo.

    Resolução, taxa e codec vêm do broker; FPS, latência e quadros perdidos são
    medidos no leitor e no worker de inferência. Campo sem medição é `None` —
    a tela mostra travessão em vez de número inventado.
    """

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
    model_error: str | None = None
    """Preenchido só no terceiro estado: havia pesos, mas a carga falhou."""
    resolution_change: ResolutionChange | None = None
    stream_error: str | None = None
    """Motivo da última desconexão do leitor; `None` enquanto há sinal."""


class FlightStatus(ApiModel):
    """Estado consolidado. É a fonte de `isFlying` para o drone 3D."""

    connected: bool
    endpoint: str
    publish_url: str
    stream_path: str
    indicators: FlightIndicators
    metrics: ConnectionMetrics
    last_seen_at: datetime | None = None


class Telemetry(ApiModel):
    """Uma amostra de posição da aeronave.

    Espelha o dataclass de `integrations/flight_source/base.py`. É o payload do
    evento SSE `flight.telemetry`, que — exceção registrada no ADR 006 — carrega
    o dado em vez de só avisar que ele mudou.
    """

    at: datetime
    latitude: float
    longitude: float
    altitude_m: float = Field(description="Relativa ao ponto de decolagem")
    heading_deg: float = Field(ge=0, lt=360, description="0 = norte, sentido horário")
    horizontal_speed_ms: float
    satellites: int
    fix_type: Literal["none", "gps", "rtk"]


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
