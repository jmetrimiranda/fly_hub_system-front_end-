"""Base declarativa e mixins comuns."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.enums import DataSource


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(UTC),
    )


class SourceMixin:
    """Marca se a linha veio do `seed.py` ou de um voo de verdade.

    Existe para que `python -m app.db.seed --clear` apague exatamente o que o
    seed criou, sem tocar em coleta real, e para que a interface possa pôr o
    selo *demonstração* onde ele é devido. O padrão é `COLLECTED` — inclusive
    nas linhas que já existiam quando a coluna entrou: elas são de voo.
    """

    source: Mapped[DataSource] = mapped_column(
        String(16), default=DataSource.COLLECTED, server_default=DataSource.COLLECTED, index=True
    )
