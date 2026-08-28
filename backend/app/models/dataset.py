"""Datasets: coletas de imagens cruas do voo, sem inferência aplicada.

O banco registra a coleta **depois** que ela termina. Durante a gravação a
verdade está em disco (`raw/` mais o `session.json` incremental): um INSERT por
quadro poria I/O de banco no caminho crítico do vídeo, e uma sessão
interrompida deixaria um dataset meio gravado em duas fontes em vez de uma.
Ver `services/collection_runtime.py`.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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

    # Parâmetros escolhidos no modal de confirmação. Guardados porque explicam
    # a forma do dataset: 500 quadros em 2 s com dedup ligado não é o mesmo
    # dataset que 500 quadros em 0,5 s sem dedup, e seis meses depois ninguém
    # lembra qual foi.
    sample_interval_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    frame_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dedup_skipped: Mapped[int] = mapped_column(Integer, default=0)
    """Quadros descartados por serem quase idênticos ao último salvo.

    Aparece na interface. Sem ele a soma não bate com o total amostrado e
    alguém perde uma tarde procurando o erro.
    """
    io_dropped: Mapped[int] = mapped_column(Integer, default=0)

    # Resultado do split temporal (ADR 004)
    train_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, default=0)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    embargo_seconds: Mapped[int] = mapped_column(Integer, default=0)
    embargo_frames: Mapped[int] = mapped_column(Integer, default=0)
    """Margem em quadros realmente aplicada — pode ser menor que a pedida."""
    embargoed_count: Mapped[int] = mapped_column(Integer, default=0)
    split_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Quando o split rodou pela última vez. Um resplit atualiza."""

    roboflow_status: Mapped[RoboflowStatus] = mapped_column(
        String(16), default=RoboflowStatus.NEVER_SENT
    )
    roboflow_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    roboflow_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    roboflow_batch: Mapped[str | None] = mapped_column(String(120), nullable=True)
    roboflow_uploaded: Mapped[int] = mapped_column(Integer, default=0)
    """Enviadas com sucesso, acumulado entre execuções.

    Retomar um lote parcial depende disto e de `DatasetImage.roboflow_sent_at`:
    300 de 500 enviadas continuam de 301, não do começo.
    """
    roboflow_failed: Mapped[int] = mapped_column(Integer, default=0)

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
    roboflow_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """Marca de envio individual. É o que permite retomar um lote parcial."""
    roboflow_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="images")


class RoboflowCredential(Base, TimestampMixin):
    """Uma chave do Roboflow gravada para reuso, cifrada em repouso.

    A coluna guarda um token Fernet, nunca a chave. Nenhum endpoint devolve o
    conteúdo dela — nem inteiro, nem mascarado: chave mascarada continua sendo
    vazamento parcial e convida a completar o resto. Ver `core/crypto.py`.
    """

    __tablename__ = "roboflow_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(80), unique=True)
    workspace: Mapped[str] = mapped_column(String(120))
    project: Mapped[str] = mapped_column(String(120))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
