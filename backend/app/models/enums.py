"""Enums do domínio, compartilhados entre modelos e schemas."""

from enum import StrEnum


class DataSource(StrEnum):
    """De onde a linha veio: do `seed.py` ou de um voo de verdade.

    Sem esta marca, distinguir demonstração de coleta real depois vira
    adivinhação — e alguém acaba treinando em cima de dado fictício. O padrão
    é `COLLECTED`: o que já existia no banco antes desta coluna foi coletado,
    e o que o seed cria diz explicitamente o contrário.
    """

    SEED = "seed"
    COLLECTED = "collected"


class CollectionStatus(StrEnum):
    RECORDING = "recording"
    PAUSED = "paused"
    SAVED = "saved"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PipelineStatus(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class SplitName(StrEnum):
    TRAIN = "train"
    VALID = "valid"
    TEST = "test"


class RoboflowStatus(StrEnum):
    NEVER_SENT = "never_sent"
    QUEUED = "queued"
    UPLOADING = "uploading"
    SENT = "sent"
    FAILED = "failed"


class InspectionStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NoteStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
