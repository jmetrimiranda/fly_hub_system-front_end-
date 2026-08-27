"""Cliente da API de status do MediaMTX.

O MediaMTX é o broker entre o FlightHub 2 (que publica RTMP) e o backend (que
consome RTSP). Perguntamos a ele quais paths estão prontos e a que taxa.
"""

from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import FlyHubUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)

# O frontend consulta o status a cada poucos segundos. Com o broker fora do ar
# isso encheria o log com a mesma linha. Registramos apenas na transicao.
_last_reachable: bool | None = None


def _log_transition(reachable: bool, url: str, error: str = "") -> None:
    global _last_reachable
    if reachable == _last_reachable:
        return
    _last_reachable = reachable
    if reachable:
        log.info("mediamtx_reachable", url=url)
    else:
        log.warning("mediamtx_unreachable", url=url, error=error)


class MediaMtxClient:
    def __init__(self, base_url: str | None = None, timeout: float = 3.0) -> None:
        self._base_url = (base_url or settings.mediamtx_api_url).rstrip("/")
        self._timeout = timeout

    async def list_paths(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/v3/paths/list")
                response.raise_for_status()
                _log_transition(True, self._base_url)
                return response.json().get("items", [])
        except httpx.HTTPError as exc:
            _log_transition(False, self._base_url, str(exc))
            raise FlyHubUnavailableError(
                "O servidor de mídia não respondeu. Verifique se o MediaMTX está no ar."
            ) from exc

    async def is_up(self) -> bool:
        try:
            await self.list_paths()
        except FlyHubUnavailableError:
            return False
        return True

    async def path_status(self, path: str) -> dict[str, Any] | None:
        for item in await self.list_paths():
            if item.get("name") == path:
                return item
        return None
