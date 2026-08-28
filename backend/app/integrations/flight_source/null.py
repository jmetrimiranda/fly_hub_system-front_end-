"""Fonte sem telemetria.

`FLIGHT_SOURCE=real` liga o MediaMTX e o vídeo de verdade, mas não a posição:
as coordenadas GPS chegam pelo FlightHub Sync (MQTT), que ainda não foi
implementado. Em vez de derrubar a aplicação, esta fonte não produz amostra
alguma — `GET /flight/telemetry` devolve 204 e o mapa fica no centro da área de
operação enquanto o resto da tela funciona normalmente.

Quando o MQTT entrar, ela sai do `match` em `__init__.py` e ninguém mais muda.
"""

from app.core.logging import get_logger

from .base import Telemetry

log = get_logger(__name__)


class NullFlightSource:
    """Implementa o protocolo `FlightSource` sem emitir nada."""

    async def start(self) -> None:
        log.info(
            "flight_source_sem_telemetria",
            motivo="FLIGHT_SOURCE=real; posição GPS depende do FlightHub Sync (MQTT)",
        )

    async def stop(self) -> None:
        return None

    async def current(self) -> Telemetry | None:
        return None
