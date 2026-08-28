"""Pipeline de inferência: liga e desliga o consumo do stream.

Este projeto não executa o modelo — apenas comanda o processo que a equipe de
visão computacional entrega, e reporta o estado. Trocar o mecanismo (processo
local, fila, serviço remoto) não deve mudar nada acima desta classe.
"""

from datetime import UTC, datetime

from app.core.config import settings
from app.core.errors import ConflictError
from app.core.events import bus
from app.core.logging import get_logger
from app.integrations.vision import detector
from app.models.enums import PipelineStatus
from app.schemas.flight import PipelineState

log = get_logger(__name__)


class PipelineService:
    """Estado em memória; ao escalar, mover para a tabela `pipeline_runs`."""

    _status: PipelineStatus = PipelineStatus.STOPPED
    _started_at: datetime | None = None
    _message: str | None = None

    @classmethod
    def state(cls) -> PipelineState:
        """O estado do modelo é o do detector, não a existência do arquivo.

        Um `best.pt` presente numa máquina sem torch existe e não carrega — a
        tela precisa distinguir "sem modelo" de "modelo não carregou". Aqui só
        `status()` é consultado, que não faz I/O além de um `stat()`; quem pode
        carregar os pesos é `VideoService.snapshot()`, fora do laço de eventos.
        """
        model = detector.status()
        loaded = bool(model["loaded"])
        return PipelineState(
            status=cls._status,
            stream_path=settings.flyhub_stream_path,
            started_at=cls._started_at,
            model_loaded=loaded,
            model_enabled=bool(model["enabled"]),
            model_version=model["weights_name"] if loaded else None,
            message=cls._message or cls._model_message(model),
        )

    @staticmethod
    def _model_message(model: dict) -> str | None:
        if model["loaded"]:
            if not model["enabled"]:
                return (
                    "Os pesos estão carregados e a inferência está desligada: o vídeo passa "
                    "cru, de propósito. Religar volta a detectar no quadro seguinte."
                )
            return None
        if model["error"]:
            return f"O modelo não carregou: {model['error']} O vídeo passa em modo passthrough."
        return "Nenhum arquivo de pesos encontrado. O vídeo passa em modo passthrough."

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
