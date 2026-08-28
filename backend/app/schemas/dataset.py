"""Schemas do domínio Dataset."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CollectionStatus, DataSource, RoboflowStatus, SplitName
from app.schemas.common import ApiModel


class SplitDistribution(ApiModel):
    train: int = 0
    valid: int = 0
    test: int = 0
    embargo_seconds: int = 0
    embargo_frames: int = 0
    embargoed: int = 0

    @property
    def total(self) -> int:
        return self.train + self.valid + self.test


class DatasetSummary(ApiModel):
    """Uma linha da tabela em Pages > Datasets."""

    id: int
    version: str
    started_at: datetime
    duration_seconds: int
    image_count: int
    disk_bytes: int
    status: CollectionStatus
    distribution: SplitDistribution
    roboflow_status: RoboflowStatus
    roboflow_sent_at: datetime | None = None
    source: DataSource = DataSource.COLLECTED
    """`seed` rende o selo *demonstração* na tela. Sem ele, alguém treina em
    cima de dado fictício sem saber."""


class DatasetImageOut(ApiModel):
    """Imagem crua, sem inferência — este fluxo nunca mistura com o de inspeção."""

    id: int
    filename: str
    captured_at: datetime
    frame_number: int
    width: int | None = None
    height: int | None = None
    size_bytes: int
    split: SplitName | None = None
    embargoed: bool = False
    roboflow_sent_at: datetime | None = None
    url: str
    """Imagem em tamanho real. Só abre no visor, nunca na grade."""
    thumb_url: str
    """Miniatura de 240 px. A grade usa esta — 500 JPEGs inteiros travam a aba."""


class SplitCounts(ApiModel):
    """Contagem por partição, contada **no disco**, na hora.

    Diverge do manifesto assim que o operador exclui uma imagem, e isso é
    esperado: o manifesto registra o que o split decidiu, não o que a pasta tem
    agora. Reescrevê-lo a cada exclusão faria o dataset deixar de ser
    reproduzível, que é a única razão de ele existir.
    """

    train: int = 0
    valid: int = 0
    test: int = 0
    raw: int = 0
    total: int = 0


class SplitWarningOut(ApiModel):
    code: str
    level: str
    message: str


class DatasetDetail(DatasetSummary):
    storage_path: str
    ended_at: datetime | None = None
    roboflow_error: str | None = None
    sample_interval_seconds: float = 2.0
    frame_limit: int | None = None
    dedup_enabled: bool = True
    dedup_skipped: int = 0
    split_at: datetime | None = None
    counts: SplitCounts
    warnings: list[SplitWarningOut] = Field(default_factory=list)
    """Avisos do último split. `level=error` significa dataset que não mede modelo."""
    drifted: bool = False
    """As contagens em disco não batem mais com o manifesto — houve exclusão."""


class DeleteImagesRequest(BaseModel):
    image_ids: list[int] = Field(min_length=1, max_length=1000)


class DeleteImagesResult(ApiModel):
    removed: int
    counts: SplitCounts
    distribution: SplitDistribution
    drifted: bool


class DeleteDatasetRequest(BaseModel):
    """Exclusão do dataset inteiro exige digitar a versão. Sem espaço para engano."""

    confirm: str = Field(min_length=1, max_length=16, examples=["v0.3"])


class ResplitResult(ApiModel):
    version: str
    counts: SplitCounts
    distribution: SplitDistribution
    warnings: list[SplitWarningOut] = Field(default_factory=list)


# --- Roboflow ----------------------------------------------------------------


class RoboflowCredentialOut(ApiModel):
    """A credencial como ela sai da API.

    Note o que **não** está aqui: a chave. Nem inteira, nem os últimos quatro
    caracteres. Não existe endpoint que a devolva.
    """

    id: int
    label: str
    workspace: str
    project: str
    created_at: datetime
    last_used_at: datetime | None = None


class RoboflowCredentialCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80, examples=["Conta da equipe"])
    workspace: str = Field(min_length=1, max_length=120)
    project: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=8, max_length=200, repr=False)
    """`repr=False` para que nem um traceback do Pydantic imprima a chave."""


class RoboflowUploadRequest(BaseModel):
    credential_id: int | None = None
    """Credencial salva. Sem ela, os campos abaixo precisam vir preenchidos."""
    workspace: str | None = None
    project: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    save_credential: bool = False
    label: str | None = None
    batch_name: str | None = None
    """Padrão: a versão do dataset."""
    tags: list[str] | None = None
    """Padrão: a versão do dataset mais `drone`."""


class RoboflowUploadResult(ApiModel):
    dataset_id: int
    status: RoboflowStatus
    uploaded: int = 0
    failed: int = 0
    pending: int = 0
    total: int = 0
    batch_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    current_file: str | None = None
    message: str | None = None
    active: bool = False
