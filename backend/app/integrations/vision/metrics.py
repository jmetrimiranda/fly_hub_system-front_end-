"""Medição do leitor e do detector.

Taxas aqui são sempre por **janela deslizante**, nunca média desde o início.
Média acumulada esconde exatamente o que interessa: uma captura que caiu de 30
para 4 fps há dez segundos continuaria exibindo 28 fps por muito tempo.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

RATE_WINDOW_S = 3.0


class RateMeter:
    """Eventos por segundo nos últimos `window` segundos."""

    def __init__(self, window: float = RATE_WINDOW_S) -> None:
        self._window = window
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._events.append(now)
            self._trim(now)

    def value(self) -> float:
        now = time.monotonic()
        with self._lock:
            self._trim(now)
            if len(self._events) < 2:
                return 0.0
            span = self._events[-1] - self._events[0]
            return round((len(self._events) - 1) / span, 1) if span > 0 else 0.0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _trim(self, now: float) -> None:
        cutoff = now - self._window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()


@dataclass(frozen=True, slots=True)
class ResolutionChange:
    """Troca de resolução no meio da transmissão.

    A causa mais comum de queda da captura: com a qualidade do canal em
    "Automático" no FlightHub, o encoder troca de perfil durante o voo e a
    sessão RTSP cai. Um dataset coletado nesse intervalo sai com resoluções
    misturadas, e nada além deste aviso denuncia isso depois.
    """

    previous: str
    current: str
    at: float
    """Epoch em segundos — o instante da troca."""


@dataclass(slots=True)
class VideoStats:
    """Retrato do pipeline de vídeo em um instante.

    É o que preenche as colunas da tabela CONEXÃO na tela Voo. Tudo aqui é
    medido, nada é estimado: quando não há medição, o campo é `None` e a tela
    mostra travessão em vez de inventar número.
    """

    connected: bool = False
    source: str | None = None
    error: str | None = None
    retry_in_seconds: float | None = None
    consumers: int = 0
    capture_fps: float | None = None
    inference_fps: float | None = None
    latency_ms: int | None = None
    dropped_frames: int = 0
    frames: int = 0
    uptime_seconds: int = 0
    resolution: str | None = None
    resolution_change: ResolutionChange | None = None
    detections: int = 0
