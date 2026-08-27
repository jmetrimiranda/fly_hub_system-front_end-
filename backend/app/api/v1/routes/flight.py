"""Pages > Voo — conexão com o FlightHub, coleta, pipeline e telemetria."""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Response, status
from sse_starlette.sse import EventSourceResponse

from app.api.v1.deps import CollectionDep, FlightDep
from app.core.events import bus
from app.schemas.common import ErrorResponse
from app.schemas.flight import (
    CollectionSession,
    EndpointUpdate,
    FlightStatus,
    PipelineState,
    Telemetry,
)
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/flight", tags=["voo"])

ERRORS = {
    409: {"model": ErrorResponse, "description": "Conflito com o estado atual"},
    503: {"model": ErrorResponse, "description": "FlightHub indisponível"},
}


# --- conexão -----------------------------------------------------------------


@router.get("/status", response_model=FlightStatus, responses=ERRORS, summary="Estado da conexão")
async def get_flight_status(service: FlightDep) -> FlightStatus:
    """Consolida os quatro indicadores e a tabela de conexão.

    `connected` é a mesma flag que vira `isFlying` no drone 3D do Dashboard.
    """
    return await service.get_status()


@router.put("/endpoint", response_model=FlightStatus, summary="Definir endereço do FlightHub")
async def update_endpoint(payload: EndpointUpdate, service: FlightDep) -> FlightStatus:
    """Grava o endereço. O frontend informa; quem conecta de fato é o backend."""
    return await service.update_endpoint(payload)


@router.get(
    "/telemetry",
    response_model=Telemetry,
    responses={204: {"description": "Nenhuma amostra produzida ainda"}},
    summary="Última posição conhecida",
)
async def get_telemetry(service: FlightDep) -> Telemetry | Response:
    """Posição inicial do mapa. As atualizações chegam pelo SSE, não por polling."""
    sample = await service.telemetry()
    return sample or Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events", summary="Telemetria em tempo real (SSE)")
async def stream_events() -> EventSourceResponse:
    """Canal Server-Sent Events com mudanças de conexão, coleta e pipeline.

    Consumido por `useServerEvents()` no frontend, que traduz cada evento na
    invalidação da chave de cache afetada. A exceção é `flight.telemetry`, que
    carrega o próprio dado — o motivo está no ADR 006.
    """

    async def publisher() -> AsyncIterator[dict[str, str]]:
        async for event in bus.subscribe():
            yield event.as_sse()

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(15)
            await bus.publish("ping")

    asyncio.create_task(heartbeat())  # noqa: RUF006
    return EventSourceResponse(publisher())


# --- coleta ------------------------------------------------------------------


@router.get("/collection/current", response_model=CollectionSession | None, summary="Coleta atual")
async def current_collection(service: CollectionDep) -> CollectionSession | None:
    dataset = await service.current()
    return CollectionSession.model_validate(dataset) if dataset else None


@router.post(
    "/collection/start",
    response_model=CollectionSession,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Coletar imagens do voo",
)
async def start_collection(service: CollectionDep) -> CollectionSession:
    """Cria a pasta da coleta e passa o estado para `recording`."""
    return await service.start()


@router.post("/collection/pause", response_model=CollectionSession, responses=ERRORS)
async def pause_collection(service: CollectionDep) -> CollectionSession:
    return await service.pause()


@router.post("/collection/resume", response_model=CollectionSession, responses=ERRORS)
async def resume_collection(service: CollectionDep) -> CollectionSession:
    return await service.resume()


@router.post(
    "/collection/save",
    response_model=CollectionSession,
    responses=ERRORS,
    summary="Salvar coleta e particionar",
)
async def save_collection(service: CollectionDep) -> CollectionSession:
    """Encerra a coleta e aplica o split temporal com embargo (ADR 004)."""
    return await service.save()


@router.post("/collection/cancel", response_model=CollectionSession, responses=ERRORS)
async def cancel_collection(service: CollectionDep) -> CollectionSession:
    return await service.cancel()


# --- pipeline ----------------------------------------------------------------


@router.get("/pipeline", response_model=PipelineState, summary="Estado do pipeline")
async def pipeline_state() -> PipelineState:
    return PipelineService.state()


@router.post("/pipeline/start", response_model=PipelineState, responses=ERRORS)
async def start_pipeline() -> PipelineState:
    return await PipelineService.start()


@router.post("/pipeline/stop", response_model=PipelineState)
async def stop_pipeline() -> PipelineState:
    return await PipelineService.stop()
