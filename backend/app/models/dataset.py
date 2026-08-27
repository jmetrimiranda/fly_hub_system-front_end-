"""Datasets: coletas de imagens cruas do voo, sem inferência aplicada."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CollectionStatus, RoboflowStatus, SplitName


class Dataset(Base, TimestampMixin):
    """Uma sessão de coleta. Vira uma versão (v0.0, v0.1, …) na página Datasets."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    flight_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("flight_sessions.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    disk_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CollectionStatus] = mapped_column(
        String(16), default=CollectionStatus.RECORDING
    )
    storage_path: Mapped[str] = mapped_column(String(512))

    # Resultado do split temporal (ADR 004)
    train_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, default=0)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    embargo_seconds: Mapped[int] = mapped_column(Integer, default=0)

    roboflow_status: Mapped[RoboflowStatus] = mapped_column(
        String(16), default=RoboflowStatus.NEVER_SENT
    )
    roboflow_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    roboflow_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    images: Mapped[list["DatasetImage"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetImage(Base):
    """Um frame cru gravado em disco. O caminho aponta para o arquivo original."""

    __tablename__ = "dataset_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(512))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    frame_number: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    split: Mapped[SplitName | None] = mapped_column(String(8), nullable=True, index=True)
    embargoed: Mapped[bool] = mapped_column(default=False)
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="images")
