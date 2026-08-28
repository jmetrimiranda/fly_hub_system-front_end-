"""Schemas do modelo de visão: estado, métricas do treino e o toggle."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class ClassMetric(ApiModel):
    """Uma classe do modelo, com o que o treino mediu para ela."""

    name: str
    map50: float | None = None
    map50_95: float | None = None
    precision: float | None = None
    recall: float | None = None


class TrainingMetrics(ApiModel):
    """O resumo de `metrics.json`, do jeito que a tela mostra.

    Todos os campos são opcionais porque o arquivo é escrito por outra pessoa,
    noutra máquina, possivelmente por uma versão anterior do notebook. Um campo
    que faltou vira travessão na tela — não uma exceção que derruba a rota.
    """

    map50: float | None = None
    map50_95: float | None = None
    precision: float | None = None
    recall: float | None = None
    classes: list[str] = []
    per_class: list[ClassMetric] = []
    trained_at: datetime | None = None
    base_model: str | None = None
    epochs: int | None = None
    dataset: str | None = None
    weights_sha256: str | None = None
    split_check_ok: bool | None = None
    """O treino conferiu se a partição do dataset baixado bateu com o split
    temporal. `False` significa métrica provavelmente otimista — ver ADR 004."""


class ModelState(ApiModel):
    """Tudo que a tela Voo precisa saber sobre o modelo, numa resposta só."""

    loaded: bool
    enabled: bool
    active: bool
    """`loaded and enabled` — se o próximo quadro vai mesmo passar pelo modelo."""
    weights_path: str
    weights_name: str
    weights_exists: bool
    classes: list[str] = []
    conf: float
    loaded_at: datetime | None = None
    error: str | None = None
    """Havia pesos e a carga falhou. O vídeo continua, em passthrough."""
    metrics: TrainingMetrics | None = None
    metrics_error: str | None = None
    message: str
    """Frase pronta para o operador. Sempre preenchida."""


class ModelToggle(BaseModel):
    enabled: bool = Field(description="Ligar ou desligar a inferência sobre o vídeo")
