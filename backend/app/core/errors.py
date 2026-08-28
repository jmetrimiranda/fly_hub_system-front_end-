"""Erros de domínio e o formato de resposta de erro da API.

Contrato único para o frontend:

    {
      "error": {
        "code": "FLYHUB_UNAVAILABLE",
        "message": "Não foi possível conectar ao FlightHub.",
        "details": {...}          # opcional, nunca com stack trace
      }
    }

`message` é escrita para o operador, em português. O rastro técnico fica no log.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base de todos os erros previstos do domínio."""

    code = "INTERNAL_ERROR"
    message = "Ocorreu um erro inesperado. Tente novamente."
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)

    def to_response(self) -> JSONResponse:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return JSONResponse(status_code=self.http_status, content={"error": payload})


class NotFoundError(AppError):
    code = "NOT_FOUND"
    message = "Recurso não encontrado."
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    code = "CONFLICT"
    message = "A operação conflita com o estado atual."
    http_status = status.HTTP_409_CONFLICT


class FlyHubUnavailableError(AppError):
    code = "FLYHUB_UNAVAILABLE"
    message = "Não foi possível conectar ao FlightHub. Verifique o endereço e o túnel."
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class CollectionStateError(ConflictError):
    code = "COLLECTION_STATE"
    message = "A coleta não está no estado necessário para esta ação."


class RoboflowError(AppError):
    code = "ROBOFLOW_ERROR"
    message = "O envio para o Roboflow falhou."
    http_status = status.HTTP_502_BAD_GATEWAY


class SecretKeyMissingError(AppError):
    code = "SECRET_KEY_MISSING"
    message = (
        "SECRET_KEY não está definida. Sem ela a chave do Roboflow não pode ser "
        "cifrada em repouso, e a aplicação não grava credencial em texto claro. "
        "Defina SECRET_KEY no .env e reinicie o backend."
    )
    http_status = status.HTTP_400_BAD_REQUEST


class DiskFullError(AppError):
    code = "DISK_FULL"
    message = "Espaço em disco insuficiente para gravar a coleta."
    http_status = status.HTTP_507_INSUFFICIENT_STORAGE


class PreflightError(ConflictError):
    """Pré-condições da coleta não atendidas.

    Os detalhes carregam a lista de verificações — é o que o modal exibe, item
    a item, com a instrução do que fazer. Uma mensagem só ("não foi possível
    iniciar") obrigaria o operador a adivinhar qual das quatro condições falhou.
    """

    code = "COLLECTION_PREFLIGHT"
    message = "Não é possível iniciar a coleta."


class SplitError(AppError):
    code = "SPLIT_ERROR"
    message = "Não foi possível particionar o dataset."
    http_status = status.HTTP_409_CONFLICT


class RoboflowNotConfiguredError(AppError):
    code = "ROBOFLOW_NOT_CONFIGURED"
    message = "Credenciais do Roboflow ausentes. Configure ROBOFLOW_API_KEY, WORKSPACE e PROJECT."
    http_status = status.HTTP_400_BAD_REQUEST


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        log.warning("app_error", code=exc.code, details=exc.details)
        return exc.to_response()

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path, error=str(exc))
        return AppError().to_response()
