"""Enums do domínio, compartilhados entre modelos e schemas."""

from enum import StrEnum


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
