"""Fachada sobre a conexão com o FlightHub.

O FlightHub 2 da DJI não expõe uma API de controle para este caso de uso: ele
publica um stream RTMP em um endereço que o operador cola no portal. O que o
backend controla, portanto, é o lado receptor — o broker de mídia e o túnel.
Esta classe existe para que os serviços falem "FlightHub" e não "MediaMTX",
e para que trocar o transporte não vaze para o resto do sistema.

Resolução e bitrate saem do encoder da aeronave e só mudam no portal da DJI.

Nota de projeto: broker fora do ar NÃO é erro aqui. "Não consegui perguntar" e
"não há stream" levam à mesma conclusão de domínio — sem sinal. Quem precisa do
broker de fato (iniciar coleta, iniciar pipeline) usa `require_broker()` e
recebe o erro. Consultar estado nunca deve derrubar uma tela.
"""

from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import FlyHubUnavailableError
from app.core.logging import get_logger
from app.integrations.mediamtx.client import MediaMtxClient

log = get_logger(__name__)


@dataclass(slots=True)
class StreamSnapshot:
    ready: bool = False
    resolution: str | None = None
    bitrate_mbps: float | None = None
    codec: str | None = None
    readers: int = 0


@dataclass(slots=True)
class FlightProbe:
    """Resultado de uma única consulta ao broker."""

    broker_up: bool = False
    stream: StreamSnapshot = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.stream is None:
            self.stream = StreamSnapshot()


# Com a fonte de voo simulada não há broker para consultar, e um `connected`
# eternamente falso esconde metade da interface. Os números são os que o
# protótipo M4TD reportava com o M4TD publicando de verdade.
FAKE_PROBE = FlightProbe(
    broker_up=True,
    stream=StreamSnapshot(
        ready=True, resolution="960x720", bitrate_mbps=0.41, codec="H264", readers=1
    ),
)


class FlyHubClient:
    def __init__(self, media: MediaMtxClient | None = None) -> None:
        self._media = media or MediaMtxClient()

    @property
    def publish_url(self) -> str:
        return settings.rtmp_publish_url

    async def probe(self, stream_path: str | None = None) -> FlightProbe:
        """Estado do broker e do stream numa única ida à rede.

        Antes eram duas: uma para saber se o broker respondia e outra para o
        path. Mesma resposta, duas chamadas e duas linhas de log por request.
        """
        if settings.flight_source == "fake":
            return FAKE_PROBE

        path = stream_path or settings.flyhub_stream_path
        try:
            items = await self._media.list_paths()
        except FlyHubUnavailableError:
            return FlightProbe(broker_up=False)

        info = next((item for item in items if item.get("name") == path), None)
        if info is None:
            return FlightProbe(broker_up=True)

        track = (info.get("tracks") or [None])[0]
        return FlightProbe(
            broker_up=True,
            stream=StreamSnapshot(
                ready=bool(info.get("ready")),
                codec=track if isinstance(track, str) else None,
                bitrate_mbps=round((info.get("bytesReceived", 0) * 8) / 1e6, 2) or None,
                readers=len(info.get("readers", [])),
            ),
        )

    async def require_broker(self) -> None:
        """Para operações que não fazem sentido sem broker. Levanta se estiver fora."""
        await self._media.list_paths()

    async def tunnel_up(self) -> bool:
        return bool(settings.tunnel_enabled and settings.tunnel_public_host)

    # Compatibilidade com chamadas antigas — preferir `probe()`.
    async def broker_up(self) -> bool:
        return (await self.probe()).broker_up

    async def snapshot(self, stream_path: str | None = None) -> StreamSnapshot:
        return (await self.probe(stream_path)).stream
