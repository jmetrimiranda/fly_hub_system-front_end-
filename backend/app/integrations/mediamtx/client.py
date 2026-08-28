"""Cliente da API de status do MediaMTX.

O MediaMTX é o broker entre o FlightHub 2 (que publica RTMP) e o backend (que
consome RTSP). Perguntamos a ele quais paths estão prontos e a que taxa.

Este módulo é o único lugar que conhece o formato de `/v3/paths/list`. Duas
correções vieram da migração do M4TD, medidas contra o broker de verdade:

* **Resolução sai de `tracks2[].codecProps`.** `tracks[]` traz só o nome do
  codec (`["H264"]`) e nenhuma dimensão — lendo dali, a coluna Resolução da
  tela Voo ficava eternamente em travessão.
* **Taxa é a derivada de `bytesReceived`, não o próprio contador.** O campo é
  cumulativo desde que o path abriu; dividi-lo por 1e6 dava "10,9 Mbps" para
  um stream de 0,4 Mbps que estava no ar há dois minutos. A taxa só existe
  entre duas amostras, e é por isso que este módulo guarda a anterior.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import FlyHubUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)

# O frontend consulta o status a cada poucos segundos. Com o broker fora do ar
# isso encheria o log com a mesma linha. Registramos apenas na transicao.
_last_reachable: bool | None = None

# Suavização da taxa: metade do valor anterior, metade da amostra nova. O
# intervalo entre consultas varia (polling do painel, revalidação por SSE), e
# sem isso a coluna Taxa oscilaria a cada request.
_RATE_SMOOTHING = 0.5

# `2026-08-28T12:49:45.751473922Z` — nove casas decimais.
_NANOSECONDS = re.compile(r"\.(\d+)")


def _log_transition(reachable: bool, url: str, error: str = "") -> None:
    global _last_reachable
    if reachable == _last_reachable:
        return
    _last_reachable = reachable
    if reachable:
        log.info("mediamtx_reachable", url=url)
    else:
        log.warning("mediamtx_unreachable", url=url, error=error)


@dataclass(slots=True)
class PathInfo:
    """Um path do MediaMTX, já traduzido para o vocabulário da plataforma."""

    name: str
    ready: bool
    resolution: str | None = None
    codec: str | None = None
    mbps: float | None = None
    readers: int = 0
    ready_seconds: int | None = None


def _resolution(item: dict[str, Any]) -> str | None:
    """`W×H` do primeiro track de vídeo que declara dimensões."""
    for track in item.get("tracks2") or []:
        props = (track or {}).get("codecProps") or {}
        width, height = props.get("width"), props.get("height")
        if width and height:
            return f"{width}×{height}"
    return None


def _codec(item: dict[str, Any]) -> str | None:
    for track in item.get("tracks2") or []:
        codec = (track or {}).get("codec") or (track or {}).get("type")
        if codec:
            return str(codec)
    tracks = item.get("tracks") or []
    return str(tracks[0]) if tracks else None


def _ready_seconds(item: dict[str, Any]) -> int | None:
    """Há quanto tempo o path está pronto, segundo o relógio do broker.

    É o tempo de stream enquanto ninguém está consumindo o RTSP: o leitor de
    quadros só abre a conexão quando há alguém olhando, e o operador ainda
    precisa saber desde quando o drone publica.
    """
    raw = item.get("readyTime")
    if not item.get("ready") or not isinstance(raw, str):
        return None
    # O MediaMTX manda nanossegundos; `fromisoformat` aceita no máximo micro.
    iso = raw.replace("Z", "+00:00")
    text = _NANOSECONDS.sub(lambda match: "." + match.group(1)[:6].ljust(6, "0"), iso, count=1)
    try:
        started = datetime.fromisoformat(text)
    except ValueError:
        return None
    return max(int((datetime.now(UTC) - started).total_seconds()), 0)


class _BitrateTracker:
    """Converte o contador cumulativo de bytes em taxa por segundo.

    Guarda a última leitura de cada path. Duas consultas próximas demais não
    produzem amostra confiável, então abaixo de `_MIN_INTERVAL_S` a taxa
    anterior é repetida em vez de recalculada.
    """

    _MIN_INTERVAL_S = 0.5

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._previous: dict[str, tuple[float, int, float]] = {}

    def observe(self, name: str, received: int) -> float | None:
        now = time.monotonic()
        with self._lock:
            previous = self._previous.get(name)
            if previous is None:
                self._previous[name] = (now, received, 0.0)
                return None

            at, before, rate = previous
            elapsed = now - at
            if elapsed < self._MIN_INTERVAL_S:
                return round(rate / 1e6, 2) or None

            delta = max(received - before, 0)
            # Contador que anda para trás significa path reaberto: recomeça.
            fresh = (delta * 8) / elapsed if received >= before else 0.0
            rate = _RATE_SMOOTHING * rate + (1 - _RATE_SMOOTHING) * fresh
            self._previous[name] = (now, received, rate)
            return round(rate / 1e6, 2) or None

    def forget(self, live: set[str]) -> None:
        with self._lock:
            for gone in set(self._previous) - live:
                del self._previous[gone]


_bitrate = _BitrateTracker()


def describe(item: dict[str, Any]) -> PathInfo:
    """Traduz um item cru de `/v3/paths/list`."""
    name = str(item.get("name") or "?")
    received = int(item.get("bytesReceived") or item.get("inboundBytes") or 0)
    return PathInfo(
        name=name,
        ready=bool(item.get("ready")),
        resolution=_resolution(item),
        codec=_codec(item),
        mbps=_bitrate.observe(name, received),
        readers=len(item.get("readers") or []),
        ready_seconds=_ready_seconds(item),
    )


class MediaMtxClient:
    def __init__(self, base_url: str | None = None, timeout: float = 3.0) -> None:
        self._base_url = (base_url or settings.mediamtx_api_url).rstrip("/")
        self._timeout = timeout

    @property
    def paths_url(self) -> str:
        return f"{self._base_url}/v3/paths/list"

    async def list_paths(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.paths_url)
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

    async def paths(self) -> list[PathInfo]:
        items = await self.list_paths()
        described = [describe(item) for item in items]
        _bitrate.forget({info.name for info in described})
        return described

    async def path_info(self, path: str) -> PathInfo | None:
        return next((info for info in await self.paths() if info.name == path), None)

    async def path_status(self, path: str) -> dict[str, Any] | None:
        for item in await self.list_paths():
            if item.get("name") == path:
                return item
        return None


class PathProbe:
    """Consulta síncrona e barata, para a thread do leitor de quadros.

    O leitor roda fora do laço de eventos e não pode `await`. Sem esta
    pergunta ele abriria um processo de FFmpeg por tentativa só para receber o
    mesmo 404 — o M4TD mediu 30 aberturas em 30 s nesse cenário. A resposta é
    cacheada por `ttl` porque o leitor consulta em laço de 1 s.

    `None` quer dizer "a API não respondeu", que é diferente de "não há path":
    o servidor RTSP pode estar servindo normalmente com a API fora do ar, e
    nesse caso vale tentar abrir.
    """

    def __init__(self, base_url: str | None = None, ttl: float = 1.0) -> None:
        self._url = f"{(base_url or settings.mediamtx_api_url).rstrip('/')}/v3/paths/list"
        self._ttl = ttl
        self._lock = threading.Lock()
        self._checked_at = 0.0
        self._items: list[dict[str, Any]] | None = None

    def _fetch(self) -> list[dict[str, Any]] | None:
        try:
            response = httpx.get(self._url, timeout=1.5)
            response.raise_for_status()
            return response.json().get("items") or []
        except (httpx.HTTPError, ValueError):
            return None

    def ready(self, path: str) -> bool | None:
        now = time.monotonic()
        with self._lock:
            stale = now - self._checked_at >= self._ttl
        if stale:
            items = self._fetch()
            with self._lock:
                self._checked_at = time.monotonic()
                self._items = items
        with self._lock:
            items = self._items
        if items is None:
            return None
        return any(item.get("name") == path and item.get("ready") for item in items)
