"""O contrato de uma fonte de telemetria de voo.

Esta é a costura entre a simulação e o hardware. Hoje existe uma implementação
(`FakeFlightSource`); quando o FlightHub Sync entrar, `MqttFlightSource`
implementa este mesmo protocolo — assina o broker, publica no `EventBus`,
guarda a última amostra — e a troca é uma linha em `flight_source/__init__.py`.
Quem consome não sabe de onde veio o dado.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

FixType = Literal["none", "gps", "rtk"]


@dataclass(slots=True)
class Telemetry:
    """Uma amostra de posição da aeronave."""

    at: datetime
    latitude: float
    longitude: float
    altitude_m: float
    """Relativa ao ponto de decolagem, não ao nível do mar."""
    heading_deg: float
    """Rumo de bússola: 0 = norte, sentido horário."""
    horizontal_speed_ms: float
    satellites: int
    fix_type: FixType


class FlightSource(Protocol):
    """Tarefa de segundo plano que produz telemetria.

    `start()` e `stop()` são chamados pelo `lifespan` da aplicação. Cada amostra
    é publicada no `EventBus` como `flight.telemetry` e guardada em memória, de
    onde `current()` a devolve — o mapa se posiciona na montagem sem esperar o
    próximo tick.
    """

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def current(self) -> Telemetry | None: ...
