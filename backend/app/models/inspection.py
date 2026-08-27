"""Inspeções: resultado do modelo de visão computacional sobre um voo."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import InspectionStatus, NoteStatus


class Inspection(Base, TimestampMixin):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    flight_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("flight_sessions.id", ondelete="SET NULL"), nullable=True
    )
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    flight_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    damage_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[InspectionStatus] = mapped_column(
        String(16), default=InspectionStatus.COMPLETED
    )
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    damages: Mapped[list["Damage"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    notes: Mapped[list["SapNote"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )

    @property
    def has_damage(self) -> bool:
        return self.damage_count > 0


class Damage(Base):
    """Uma avaria detectada. Vem pronta do serviço de visão computacional."""

    __tablename__ = "damages"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    frame_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    inspection: Mapped[Inspection] = relationship(back_populates="damages")


class SapNote(Base, TimestampMixin):
    """Nota SAP aberta a partir de uma inspeção."""

    __tablename__ = "sap_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), index=True
    )
    sap_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[NoteStatus] = mapped_column(String(16), default=NoteStatus.OPEN, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    inspection: Mapped[Inspection] = relationship(back_populates="notes")


class ModelMetric(Base, TimestampMixin):
    """Métricas publicadas pela equipe de visão computacional (MAPE, mAP, …).

    Este projeto não treina o modelo — apenas registra e exibe o que a outra
    camada informa.
    """

    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    metric: Mapped[str] = mapped_column(String(32), default="mape")
    value: Mapped[float] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
