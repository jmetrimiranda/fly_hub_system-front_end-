"""Fonte de telemetria simulada.

Existe porque a conexão real com o FlightHub vive em outro projeto: sem ela,
metade da interface — drone decolando, hélices acelerando, mapa com a posição —
nunca foi vista por ninguém. Com `FLIGHT_SOURCE=fake` a aplicação inteira se
comporta como conectada, sem hardware.

É descartável por construção. Nada aqui é regra de negócio: o que sai é uma
sequência de `Telemetry`, exatamente o que o broker MQTT vai produzir.

A rota é uma varredura do píer do Terminal Marítimo de Ponta Ubu: decola do
centro, entra na área, faz quatro passadas paralelas e volta para pousar. Ao
fechar o ciclo recomeça — a tela precisa continuar viva indefinidamente.
"""

import asyncio
import contextlib
import math
import random
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import pairwise

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger

from .base import Telemetry

log = get_logger(__name__)

# Conversão metro → grau. A latitude é praticamente constante numa área de
# algumas centenas de metros, então uma aproximação plana basta e evita
# arrastar uma dependência geodésica para dentro do projeto.
METERS_PER_DEG_LAT = 110_900.0
METERS_PER_DEG_LON_EQUATOR = 111_320.0


def meters_per_deg_lon(latitude: float) -> float:
    """≈ 104_060 na latitude de Ponta Ubu (-20,79°)."""
    return METERS_PER_DEG_LON_EQUATOR * math.cos(math.radians(latitude))


@dataclass(frozen=True, slots=True)
class Waypoint:
    """Posição em metros relativos ao centro configurado. Leste e norte."""

    east_m: float
    north_m: float
    altitude_m: float


# Altitude interpola ao longo da perna, então a subida acontece durante a
# entrada na área e a descida durante o retorno — não parado no ponto.
ROUTE: tuple[Waypoint, ...] = (
    Waypoint(0, 0, 0),  # 0 decolagem
    Waypoint(-150, 80, 60),  # 1 entrada na área
    Waypoint(250, 80, 60),  # 2 passada 1
    Waypoint(250, 40, 60),  # 3
    Waypoint(-150, 40, 60),  # 4 passada 2
    Waypoint(-150, 0, 60),  # 5
    Waypoint(250, 0, 60),  # 6 passada 3
    Waypoint(250, -40, 60),  # 7
    Waypoint(-150, -40, 60),  # 8 passada 4
    Waypoint(0, 0, 0),  # 9 retorno e pouso — mesmo ponto do 0, o ciclo fecha
)

POSITION_NOISE_M = 0.4
"""Sem ruído o traçado sai perfeito demais e não exercita a suavização do mapa."""

SATELLITES_MIN = 18
SATELLITES_MAX = 26


class FakeFlightSource:
    """Implementa `FlightSource` percorrendo `ROUTE` em velocidade constante."""

    def __init__(
        self,
        *,
        center: tuple[float, float] | None = None,
        interval_s: float | None = None,
        speed_ms: float | None = None,
        seed: int = 42,  # o mesmo do seed.py — o voo simulado é reprodutível
    ) -> None:
        self._center_lat, self._center_lon = center or (
            settings.fake_flight_center_lat,
            settings.fake_flight_center_lon,
        )
        self._interval = interval_s if interval_s is not None else settings.fake_flight_interval
        self._speed = speed_ms if speed_ms is not None else settings.fake_flight_speed_ms
        self._random = random.Random(seed)  # noqa: S311 — simulação, não criptografia
        self._meters_per_deg_lon = meters_per_deg_lon(self._center_lat)

        self._legs = self._build_legs()
        self._perimeter = sum(length for _, _, length in self._legs)
        self._travelled = 0.0
        self._tick = 0
        self._last: Telemetry | None = None
        self._task: asyncio.Task[None] | None = None

    # --- ciclo de vida -------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        log.info(
            "fake_flight_started",
            interval_s=self._interval,
            speed_ms=self._speed,
            perimeter_m=round(self._perimeter),
        )

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        log.info("fake_flight_stopped")

    async def current(self) -> Telemetry | None:
        return self._last

    # --- produção de amostras ------------------------------------------------

    async def _run(self) -> None:
        while True:
            sample = self.sample()
            self._last = sample
            # O evento carrega o dado (ADR 006). `at` fica de fora: o EventBus
            # carimba o instante e assim existe uma única fonte para ele.
            payload = asdict(sample)
            payload.pop("at")
            await bus.publish("flight.telemetry", **payload)

            await asyncio.sleep(self._interval)
            self._advance()

    def _advance(self) -> None:
        self._tick += 1
        self._travelled = (self._travelled + self._speed * self._interval) % self._perimeter

    def sample(self) -> Telemetry:
        """Amostra na posição atual da rota. Pública para os testes."""
        east, north, altitude, heading = self._locate(self._travelled)
        east += self._random.gauss(0.0, POSITION_NOISE_M)
        north += self._random.gauss(0.0, POSITION_NOISE_M)

        return Telemetry(
            at=datetime.now(UTC),
            latitude=self._center_lat + north / METERS_PER_DEG_LAT,
            longitude=self._center_lon + east / self._meters_per_deg_lon,
            altitude_m=round(altitude, 1),
            heading_deg=heading,
            horizontal_speed_ms=self._speed,
            satellites=self._satellites(),
            fix_type="rtk",
        )

    def _satellites(self) -> int:
        """Oscila devagar entre 18 e 26 — só para a interface não parecer congelada."""
        span = (SATELLITES_MAX - SATELLITES_MIN) / 2
        return SATELLITES_MIN + round(span * (1 + math.sin(self._tick / 7)))

    # --- geometria da rota ---------------------------------------------------

    @staticmethod
    def _build_legs() -> list[tuple[Waypoint, Waypoint, float]]:
        legs = []
        for start, end in pairwise(ROUTE):
            length = math.hypot(end.east_m - start.east_m, end.north_m - start.north_m)
            if length > 0:
                legs.append((start, end, length))
        return legs

    def _locate(self, distance: float) -> tuple[float, float, float, float]:
        """Interpola posição, altitude e rumo a `distance` metros do início."""
        remaining = distance
        for start, end, length in self._legs:
            if remaining > length:
                remaining -= length
                continue
            ratio = remaining / length
            east = start.east_m + (end.east_m - start.east_m) * ratio
            north = start.north_m + (end.north_m - start.north_m) * ratio
            altitude = start.altitude_m + (end.altitude_m - start.altitude_m) * ratio
            return east, north, altitude, self._heading(start, end)

        # Só alcançável por erro de arredondamento no fim da última perna.
        last = ROUTE[-1]
        start, end, _ = self._legs[-1]
        return last.east_m, last.north_m, last.altitude_m, self._heading(start, end)

    @staticmethod
    def _heading(start: Waypoint, end: Waypoint) -> float:
        """Rumo de bússola do deslocamento: 0 = norte, horário."""
        bearing = math.degrees(math.atan2(end.east_m - start.east_m, end.north_m - start.north_m))
        return bearing % 360.0
