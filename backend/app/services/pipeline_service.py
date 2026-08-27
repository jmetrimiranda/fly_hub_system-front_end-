"""Pipeline de inferência: liga e desliga o consumo do stream.

Este projeto não executa o modelo — apenas comanda o processo que a equipe de
visão computacional entrega, e reporta o estado. Trocar o mecanismo (processo
local, fila, serviço remoto) não deve mudar nada acima desta classe.
"""

from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.errors import ConflictError
from app.core.events import bus
from app.core.logging import get_logger
from app.models.enums import PipelineStatus
from app.schemas.flight import PipelineState

log = get_logger(__name__)


class PipelineService:
    """Estado em memória; ao escalar, mover para a tabela `pipeline_runs`."""

    _status: PipelineStatus = PipelineStatus.STOPPED
    _started_at: datetime | None = None
    _message: str | None = None

    @classmethod
    def _weights_path(cls) -> Path:
        return settings.models_dir / "best.pt"

    @classmethod
    def state(cls) -> PipelineState:
        weights = cls._weights_path()
        loaded = weights.exists()
        return PipelineState(
            status=cls._status,
            stream_path=settings.flyhub_stream_path,
            started_at=cls._started_at,
            model_loaded=loaded,
            model_version=weights.stem if loaded else None,
            message=cls._message
            or (
                None
                if loaded
                else "Nenhum arquivo de pesos encontrado. O vídeo passa em modo passthrough."
            ),
        )

    @classmethod
    async def start(cls) -> PipelineState:
        if cls._status == PipelineStatus.RUNNING:
            raise ConflictError("O pipeline já está em execução.")
        cls._status = PipelineStatus.RUNNING
        cls._started_at = datetime.now(UTC)
        cls._message = None
        await bus.publish("pipeline.status", status=cls._status)
        log.info("pipeline_started", stream=settings.flyhub_stream_path)
        return cls.state()

    @classmethod
    async def stop(cls) -> PipelineState:
        cls._status = PipelineStatus.STOPPED
        cls._started_at = None
        await bus.publish("pipeline.status", status=cls._status)
        log.info("pipeline_stopped")
        return cls.state()
