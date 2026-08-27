"""Fachada sobre a conexão com o FlightHub.

O FlightHub 2 da DJI não expõe uma API de controle para este caso de uso: ele
publica um stream RTMP em um endereço que o operador cola no portal. O que o
backend controla, portanto, é o lado receptor — o broker de mídia e o túnel.
Esta classe existe para que os serviços falem "FlightHub" e não "MediaMTX",
e para que trocar o transporte não vaze para o resto do sistema.

Resolução e bitrate saem do encoder da aeronave e só mudam no portal da DJI.
"""

from dataclasses import dataclass

from app.core.config import settings
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


class FlyHubClient:
    def __init__(self, media: MediaMtxClient | None = None) -> None:
        self._media = media or MediaMtxClient()

    @property
    def publish_url(self) -> str:
        return settings.rtmp_publish_url

    async def broker_up(self) -> bool:
        return await self._media.is_up()

    async def tunnel_up(self) -> bool:
        return bool(settings.tunnel_enabled and settings.tunnel_public_host)

    async def snapshot(self, stream_path: str | None = None) -> StreamSnapshot:
        path = stream_path or settings.flyhub_stream_path
        info = await self._media.path_status(path)
        if not info:
            return StreamSnapshot()

        track = (info.get("tracks") or [None])[0]
        return StreamSnapshot(
            ready=bool(info.get("ready")),
            codec=track if isinstance(track, str) else None,
            bitrate_mbps=round((info.get("bytesReceived", 0) * 8) / 1e6, 2) or None,
            readers=len(info.get("readers", [])),
        )
