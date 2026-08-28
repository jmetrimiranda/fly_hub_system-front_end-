"""Ponto de entrada da API.

As rotas só orquestram: validam a entrada, chamam um service e devolvem um
schema. Regra de negócio dentro de rota não é testável sem subir a aplicação.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.integrations.flight_source import get_flight_source
from app.services.collection_runtime import recorder
from app.services.video_service import VideoService

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.datasets_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    source = get_flight_source()
    await source.start()

    # As threads sobem ociosas: o RTSP só é aberto quando alguém pede o vídeo
    # ou uma coleta começa. Com `FLIGHT_SOURCE=fake` nem isso acontece.
    VideoService.start()

    log.info(
        "api_started",
        env=settings.app_env,
        prefix=settings.api_prefix,
        flight_source=settings.flight_source,
    )
    yield

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
