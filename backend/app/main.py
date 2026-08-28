"""Ponto de entrada da API.

As rotas só orquestram: validam a entrada, chamam um service e devolvem um
schema. Regra de negócio dentro de rota não é testável sem subir a aplicação.
"""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.integrations.flight_source import get_flight_source
from app.services import model_service
from app.services.collection_runtime import recorder
from app.services.model_service import ModelService
from app.services.video_service import VideoService

configure_logging()
log = get_logger(__name__)


def _ensure_dir(path, what: str) -> None:
    """Cria a pasta se der. Não dar é aviso, não é motivo para não subir."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning(
            "pasta_indisponivel",
            path=str(path),
            para=what,
            error=f"{type(exc).__name__}: {exc}",
            dica="recrie o container para aplicar os volumes do compose",
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _ensure_dir(settings.datasets_dir, "coletas")
    # `models/` chega por bind mount e não existe até o container ser recriado
    # (`up -d --force-recreate backend`). Faltando, a aplicação sobe igual: o
    # detector trata ausência de pesos como o estado inicial do projeto, não
    # como erro. Derrubar a API porque não há modelo seria inverter isso.
    _ensure_dir(settings.models_dir, "pesos do modelo")

    source = get_flight_source()
    await source.start()

    # As threads sobem ociosas: o RTSP só é aberto quando alguém pede o vídeo
    # ou uma coleta começa. Com `FLIGHT_SOURCE=fake` nem isso acontece.
    VideoService.start()

    # O toggle da inferência é do operador, não do processo: subir não pode
    # religar um modelo que alguém desligou de propósito antes do reinício.
    # Um banco indisponível no start não impede a API de subir — o padrão
    # (ligado) vale, e o log diz o que aconteceu.
    async with SessionLocal() as session:
        try:
            await ModelService(session).restore()
        except Exception as exc:  # pragma: no cover — banco fora do ar no start
            log.warning("model_toggle_nao_restaurado", error=f"{type(exc).__name__}: {exc}")

    # Vigia dos pesos: é ele que faz "copie o best.pt e o badge muda em
    # segundos" ser verdade com o vídeo fechado. Ver `services/model_service.py`.
    watcher = asyncio.create_task(model_service.watch(), name="model-watch")

    log.info(
        "api_started",
        env=settings.app_env,
        prefix=settings.api_prefix,
        flight_source=settings.flight_source,
    )
    yield

    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher

    # Uma coleta em andamento durante o desligamento não perde o que já está em
    # disco: o `session.json` é gravado e `raw/` fica consistente. O split roda
    # depois, pelo botão Refazer split do dataset.
    recorder.shutdown()
    VideoService.stop()
    await source.stop()
    log.info("api_stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API da plataforma de inspeções por drone. "
        "Documentação completa em https://flyhub-docs.pages.dev"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)
