"""A fonte de voo simulada.

O que importa aqui não é o traçado exato — é que a simulação seja plausível o
bastante para exercitar a interface: dentro da área de operação, com rumo
válido, andando na velocidade configurada e fechando o ciclo sem teleporte.
"""

import asyncio
import math
from itertools import pairwise

import pytest

from app.core.config import settings
from app.core.events import bus
from app.integrations.flight_source import create_flight_source
from app.integrations.flight_source.base import Telemetry
from app.integrations.flight_source.fake import (
    METERS_PER_DEG_LAT,
    ROUTE,
    FakeFlightSource,
    meters_per_deg_lon,
)

CENTER = (settings.fake_flight_center_lat, settings.fake_flight_center_lon)
INTERVAL = 1.0
SPEED = 6.0


def build() -> FakeFlightSource:
    return FakeFlightSource(center=CENTER, interval_s=INTERVAL, speed_ms=SPEED)


def offset_m(sample: Telemetry) -> tuple[float, float]:
    """Volta de graus para metros relativos ao centro, como leste e norte."""
    east = (sample.longitude - CENTER[1]) * meters_per_deg_lon(CENTER[0])
    north = (sample.latitude - CENTER[0]) * METERS_PER_DEG_LAT
    return east, north


def lap(source: FakeFlightSource, laps: float = 1.0) -> list[Telemetry]:
    """Amostras de uma volta completa, sem esperar relógio nenhum."""
    steps = math.ceil(source._perimeter * laps / (SPEED * INTERVAL))
    samples = []
    for _ in range(steps):
        samples.append(source.sample())
        source._advance()
    return samples


def test_the_whole_route_stays_inside_the_operating_area():
    for sample in lap(build()):
        east, north = offset_m(sample)
        assert math.hypot(east, north) < 500


def test_heading_is_always_a_valid_compass_bearing():
    for sample in lap(build()):
        assert 0.0 <= sample.heading_deg < 360.0


def test_altitude_climbs_on_takeoff_and_returns_to_the_ground():
    samples = lap(build())
    assert samples[0].altitude_m == pytest.approx(0.0, abs=0.5)
    assert max(s.altitude_m for s in samples) == pytest.approx(60.0, abs=1.0)
    assert min(s.altitude_m for s in samples) == pytest.approx(0.0, abs=0.5)


def test_the_route_closes_the_cycle_and_restarts_without_jumping():
    # Duas voltas: a emenda entre elas não pode ser distinguível de um passo normal.
    samples = lap(build(), laps=2.0)
    steps = [
        math.dist(offset_m(a), offset_m(b)) for a, b in pairwise(samples)
    ]
    assert max(steps) < SPEED * INTERVAL * 1.5

    # O último waypoint é o primeiro: a rota volta ao ponto de decolagem.
    assert (ROUTE[-1].east_m, ROUTE[-1].north_m) == (ROUTE[0].east_m, ROUTE[0].north_m)


def test_consecutive_samples_move_at_the_configured_speed():
    samples = lap(build())
    steps = [
        math.dist(offset_m(a), offset_m(b)) for a, b in pairwise(samples)
    ]
    expected = SPEED * INTERVAL
    # Em curva a corda é menor que o arco, então a média é o que se compara.
    assert sum(steps) / len(steps) == pytest.approx(expected, rel=0.1)
    assert max(steps) < expected * 1.5


def test_satellites_and_fix_stay_within_the_declared_range():
    for sample in lap(build()):
        assert 18 <= sample.satellites <= 26
        assert sample.fix_type == "rtk"


async def test_current_is_none_before_start():
    source = build()
    assert await source.current() is None


async def test_start_publishes_on_the_bus_and_stop_ends_the_task():
    source = FakeFlightSource(center=CENTER, interval_s=0.01, speed_ms=SPEED)
    await source.start()
    # O assinante só entra na fila no primeiro `anext`; com a fonte publicando a
    # cada 10 ms, a próxima amostra chega logo em seguida.
    stream = bus.subscribe()

    try:
        event = await asyncio.wait_for(anext(stream), timeout=2)
    finally:
        await source.stop()
        await stream.aclose()

    assert event.type == "flight.telemetry"
    # O evento carrega o dado (ADR 006), não só o aviso de que ele mudou.
    assert event.payload["latitude"] == pytest.approx(CENTER[0], abs=0.01)
    assert event.payload["longitude"] == pytest.approx(CENTER[1], abs=0.01)
    assert await source.current() is not None


async def test_stopping_twice_is_harmless():
    source = build()
    await source.stop()
    await source.start()
    await source.stop()
    await source.stop()


def test_mqtt_source_says_where_to_implement_it(monkeypatch):
    monkeypatch.setattr(settings, "flight_source", "mqtt")
    with pytest.raises(NotImplementedError, match="MqttFlightSource"):
        create_flight_source()
