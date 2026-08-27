"""Fonte de telemetria de voo.

Um único ponto escolhe a implementação. Trocar simulação por broker real é
mudar o `match` abaixo — nenhum service, rota ou componente sabe a diferença.
"""

from functools import lru_cache

from app.core.config import settings

from .base import FixType, FlightSource, Telemetry
from .fake import FakeFlightSource

__all__ = [
    "FakeFlightSource",
    "FixType",
    "FlightSource",
    "Telemetry",
    "create_flight_source",
    "get_flight_source",
]


def create_flight_source() -> FlightSource:
    if settings.flight_source == "fake":
        return FakeFlightSource()
    raise NotImplementedError(
        "FLIGHT_SOURCE=mqtt ainda não foi implementado. A conexão com o FlightHub "
        "Sync entra como MqttFlightSource em app/integrations/flight_source/mqtt.py, "
        "implementando o protocolo FlightSource de base.py, e é registrada aqui. "
        "Use FLIGHT_SOURCE=fake enquanto isso."
    )


@lru_cache
def get_flight_source() -> FlightSource:
    """Instância única do processo — o `lifespan` a inicia e para."""
    return create_flight_source()
