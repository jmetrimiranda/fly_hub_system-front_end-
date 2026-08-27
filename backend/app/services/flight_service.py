"""Regras do domínio Voo: conexão, indicadores e telemetria."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger
from app.integrations.flight_source import FlightSource, get_flight_source
from app.integrations.flyhub.client import FlyHubClient
from app.models.flight import FlightConnection
from app.schemas.flight import (
    ConnectionMetrics,
    EndpointUpdate,
    FlightIndicators,
    FlightStatus,
    Telemetry,
)

log = get_logger(__name__)


class FlightService:
    def __init__(
        self,
        session: AsyncSession,
        client: FlyHubClient | None = None,
        source: FlightSource | None = None,
    ) -> None:
        self._session = session
        self._client = client or FlyHubClient()
        self._source = source or get_flight_source()

    async def _connection(self) -> FlightConnection:
        result = await self._session.execute(select(FlightConnection).limit(1))
        connection = result.scalar_one_or_none()
        if connection is None:
            connection = FlightConnection(
                id=1, endpoint=settings.rtmp_publish_url, stream_path=settings.flyhub_stream_path
            )
            self._session.add(connection)
            await self._session.commit()
        return connection

    async def get_status(self) -> FlightStatus:
        """Estado consolidado da conexão. É a fonte de `isFlying` do drone 3D."""
        connection = await self._connection()
        probe = await self._client.probe(connection.stream_path)
        tunnel_up = await self._client.tunnel_up()

        broker_up, stream = probe.broker_up, probe.stream
        connected = broker_up and stream.ready
        if connected != connection.connected:
            connection.connected = connected
            connection.last_seen_at = datetime.now(UTC) if connected else connection.last_seen_at
            await self._session.commit()
            await bus.publish("flight.connection", connected=connected)
            log.info("flight_connection_changed", connected=connected)

        indicators = FlightIndicators(
            availability=connected,
            mediamtx_up=broker_up,
            tunnel_up=tunnel_up,
            stream_up=stream.ready,
            availability_label=(
                f"Recebendo — {stream.bitrate_mbps} Mbps" if connected else "Sem sinal"
            ),
            mediamtx_label="No ar" if broker_up else "Fora do ar",
            tunnel_label=settings.tunnel_public_host or "desligado",
            stream_label=connection.stream_path,
        )

        return FlightStatus(
            connected=connected,
            endpoint=connection.endpoint,
            publish_url=self._client.publish_url,
            stream_path=connection.stream_path,
            indicators=indicators,
            metrics=ConnectionMetrics(
                resolution=stream.resolution,
                bitrate_mbps=stream.bitrate_mbps,
                codec=stream.codec,
            ),
            last_seen_at=connection.last_seen_at,
        )

    async def telemetry(self) -> Telemetry | None:
        """Última amostra conhecida, ou `None` se a fonte ainda não produziu uma.

        O mapa chama isto na montagem para se posicionar sem esperar o próximo
        tick; daí em diante ele vive do evento SSE.
        """
        sample = await self._source.current()
        return Telemetry.model_validate(sample) if sample else None

    async def update_endpoint(self, payload: EndpointUpdate) -> FlightStatus:
        """Grava o endereço informado pelo operador. Quem conecta é o backend."""
        connection = await self._connection()
        connection.endpoint = payload.endpoint
        await self._session.commit()
        await bus.publish("flight.endpoint", endpoint=payload.endpoint)
        log.info("flight_endpoint_updated", endpoint=payload.endpoint)
        return await self.get_status()
