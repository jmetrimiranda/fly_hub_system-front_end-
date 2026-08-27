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

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.datasets_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    log.info("api_started", env=settings.app_env, prefix=settings.api_prefix)
    yield
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
