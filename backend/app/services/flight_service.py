"""Regras do domínio Voo: conexão, indicadores e telemetria."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger
from app.integrations.flight_source import FlightSource, get_flight_source
from app.integrations.flyhub.client import FlyHubClient, StreamSnapshot
from app.models.flight import FlightConnection
from app.schemas.flight import (
    ConnectionMetrics,
    EndpointUpdate,
    FlightIndicators,
    FlightStatus,
    ResolutionChange,
    Telemetry,
)
from app.services.video_service import VideoService

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
            connection = FlightConnection(id=1, endpoint=settings.rtmp_publish_url)
            self._session.add(connection)
            await self._session.commit()
        return connection

    async def get_status(self) -> FlightStatus:
        """Estado consolidado da conexão. É a fonte de `isFlying` do drone 3D."""
        connection = await self._connection()
        probe = await self._client.probe(settings.flyhub_stream_path)
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
            availability_label=self._availability_label(connected, stream.bitrate_mbps),
            mediamtx_label="No ar" if broker_up else "Fora do ar",
            tunnel_label=self._tunnel_label(tunnel_up),
            stream_label=settings.flyhub_stream_path,
        )

        return FlightStatus(
            connected=connected,
            endpoint=connection.endpoint,
            publish_url=self._client.publish_url,
            stream_path=settings.flyhub_stream_path,
            indicators=indicators,
            metrics=await self._metrics(stream),
            last_seen_at=connection.last_seen_at,
        )

    @staticmethod
    def _availability_label(connected: bool, bitrate_mbps: float | None) -> str:
        if not connected:
            return "Sem sinal"
        # A taxa só existe depois de duas amostras do contador de bytes: na
        # primeira consulta depois de subir, ainda não há derivada para exibir.
        return f"Recebendo — {bitrate_mbps} Mbps" if bitrate_mbps else "Recebendo"

    @staticmethod
    def _tunnel_label(tunnel_up: bool) -> str:
        """O túnel deixou de ser obrigatório quando o M4TD passou a usar um
        endereço público fixo. Com ele definido, "desligado" seria enganoso: o
        túnel não está faltando, está dispensado."""
        if tunnel_up:
            return settings.tunnel_public_host
        if settings.flyhub_public_host:
            return f"dispensado — {settings.flyhub_public_host}"
        return "desligado"

    async def _metrics(self, stream: StreamSnapshot) -> ConnectionMetrics:
        """Junta o que o broker sabe com o que o leitor de quadros mede.

        Resolução, taxa e codec são do broker — ele enxerga o publicador mesmo
        com ninguém assistindo. FPS, latência e quadros perdidos só existem
        enquanto o leitor está consumindo o RTSP, o que acontece quando alguém
        abre o vídeo na tela Voo ou uma coleta está gravando.
        """
        snapshot = await VideoService.snapshot()
        video = snapshot.stats
        change = video.resolution_change

        return ConnectionMetrics(
            resolution=stream.resolution or video.resolution,
            bitrate_mbps=stream.bitrate_mbps,
            capture_fps=video.capture_fps,
            inference_fps=video.inference_fps,
            latency_ms=video.latency_ms,
            dropped_frames=video.dropped_frames,
            # O tempo de stream do leitor conta desde que ele abriu o RTSP; sem
            # leitor no ar vale o relógio do broker, que conta desde que o
            # publicador chegou.
            stream_uptime_seconds=video.uptime_seconds or stream.ready_seconds or 0,
            codec=stream.codec,
            model_loaded=snapshot.model_loaded,
            model_version=snapshot.model_version,
            model_error=snapshot.model_error,
            resolution_change=(
                ResolutionChange(
                    previous=change.previous,
                    current=change.current,
                    at=datetime.fromtimestamp(change.at, UTC),
                )
                if change
                else None
            ),
            stream_error=video.error,
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
