"""Voo: configuração da conexão, sessões de voo e amostras de telemetria."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FlightConnection(Base, TimestampMixin):
    """Configuração da conexão com o FlightHub. Linha única (id=1)."""

    __tablename__ = "flight_connection"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    endpoint: Mapped[str] = mapped_column(String(255), default="")
    stream_path: Mapped[str] = mapped_column(String(120), default="live/m4td")
    tunnel_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FlightSession(Base, TimestampMixin):
    """Uma janela contínua de stream recebido do FlightHub."""

    __tablename__ = "flight_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bitrate_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dropped_frames: Mapped[int] = mapped_column(Integer, default=0)

    telemetry: Mapped[list["TelemetrySample"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class TelemetrySample(Base):
    """Amostra periódica dos indicadores da página Voo.

    Alimenta os cards Disponibilidade / MediaMTX / Túnel / Stream e a tabela de
    conexão. Retenção curta — ver `docs/flight.md`.
    """

    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("flight_sessions.id", ondelete="CASCADE"), index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    capture_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    inference_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    dropped_frames: Mapped[int] = mapped_column(Integer, default=0)
    availability: Mapped[bool] = mapped_column(Boolean, default=False)
    mediamtx_up: Mapped[bool] = mapped_column(Boolean, default=False)
    tunnel_up: Mapped[bool] = mapped_column(Boolean, default=False)
    stream_up: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[FlightSession] = relationship(back_populates="telemetry")
