"""Tipos compartilhados entre schemas."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base com `from_attributes` — todo schema de saída herda daqui."""

    model_config = ConfigDict(from_attributes=True)


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Documenta no OpenAPI o formato de erro que o frontend espera."""

    error: ErrorBody


class TimePoint(ApiModel):
    date: datetime
    value: float = Field(description="Valor agregado no período")
