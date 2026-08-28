"""Leitor de quadros RTSP.

Portado de `app/video.py` do M4TD. O arranjo é o mesmo:

```text
RTSP ──► leitor (thread) ──► slot de 1 quadro ──► worker (stream.py)
         sempre o mais       publicar sobrescreve
         recente             e conta como perdido
```

Entre os estágios há um **slot de um quadro, não uma fila**. É isso que impede
a latência de acumular quando a inferência é mais lenta que o stream: o quadro
velho é sobrescrito e contabilizado como perdido, e quem consome sempre pega o
mais recente. Com fila nada se perderia — e a latência cresceria sem teto.

Duas decisões vieram medidas do protótipo e não devem ser desfeitas:

* **O backoff é zerado por um quadro lido, não por uma conexão aberta.** Um
  path que abre e nunca entrega quadro (publicador que caiu sem o MediaMTX
  derrubar o path) reiniciava o backoff a cada ciclo: 30 aberturas de RTSP em
  30 s, cada uma custando um FFmpeg inteiro. Zerando só depois de `read()`
  devolver imagem, as mesmas condições dão 6 tentativas — 1, 2, 4, 8, 10 s.
* **O leitor não tenta abrir quando o broker diz que não há path.** Nesse
  estado a espera é de 1 s relendo o cache do `PathProbe`, e não o backoff
  acumulado — o que também faz a captura recomeçar quase imediatamente quando
  o drone volta a publicar.
"""

from __future__ import annotations

import itertools
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.mediamtx.client import PathProbe

from .metrics import RateMeter, ResolutionChange, VideoStats

log = get_logger(__name__)

# rtsp_transport=tcp evita perda de pacotes em UDP; stimeout impede que um
# servidor morto deixe o VideoCapture pendurado indefinidamente na abertura.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000"
)

RECONNECT_MIN_S = 1.0
RECONNECT_MAX_S = 10.0
IDLE_CLOSE_S = 10.0
"""Sem nenhum consumidor por esse tempo, o RTSP é liberado."""
NO_PATH_POLL_S = 1.0
NO_PATH_MESSAGE = "nenhum path publicando no MediaMTX"
RESOLUTION_WARNING_S = 300.0
"""O aviso de troca de resolução some sozinho depois disso, sem nova troca."""
IDLE_TICK_S = 0.25


def next_backoff(current: float) -> float:
    """Dobra até o teto. Exponencial com saturação, nunca acima de 10 s."""
    return min(current * 2, RECONNECT_MAX_S)


@dataclass(slots=True)
class Frame:
    """Um quadro decodificado e o instante em que foi capturado.

    O instante viaja junto com a imagem para medir a latência de ponta a ponta
    e, na coleta, nomear o arquivo com o tempo relativo ao início da captura —
    que é o que permite o split temporal por blocos contíguos.
    """

    image: Any
    seq: int
    captured_at: float
    """`time.monotonic()`, para medir intervalos."""
    captured_epoch: float
    """`time.time()`, para datar em disco."""
    session_started_at: float
    """Monotonic de quando esta conexão RTSP abriu."""

    @property
    def elapsed(self) -> float:
        return self.captured_at - self.session_started_at

    @property
    def size(self) -> tuple[int, int]:
        height, width = self.image.shape[:2]
        return width, height


class FrameSlot:
    """Espaço para exatamente um item. Publicar sobrescreve; ninguém enfileira."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._item: Any = None
        self._seq = 0
        self._taken = True
        self.dropped = 0

    def publish(self, item: Any) -> None:
        with self._condition:
            if not self._taken:
                self.dropped += 1  # ninguém consumiu o anterior
            self._item = item
            self._seq += 1
            self._taken = False
            self._condition.notify_all()

    def take(self, last_seq: int, timeout: float) -> tuple[Any, int] | None:
        """Bloqueia até haver item mais novo que `last_seq`. `None` no timeout."""
        with self._condition:
            if self._seq == last_seq:
                self._condition.wait(timeout)
            if self._seq == last_seq or self._item is None:
                return None
            self._taken = True
            return self._item, self._seq

    def peek(self) -> Any:
        with self._condition:
            return self._item

    def clear(self) -> None:
        with self._condition:
            self._item = None
            self._taken = True


@dataclass(slots=True)
class _Consumer:
    kind: str
    label: str
    since: float = field(default_factory=time.time)


class Consumers:
    """Quem precisa do RTSP aberto.

    Dois tipos: `mjpeg` (um por resposta multipart aberta) e `collect` (uma
    sessão de gravação). A decisão de fechar olha o **total**, nunca a contagem
    de clientes HTTP: durante uma coleta pode não haver navegador nenhum aberto
    e o leitor tem que continuar. `collect` já é aceito aqui; quem o registra
    entra com a coleta de quadros, na fase seguinte da migração.
    """

    KINDS = ("mjpeg", "collect")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._entries: dict[int, _Consumer] = {}

    def add(self, kind: str, label: str | None = None) -> int:
        if kind not in self.KINDS:
            raise ValueError(f"consumidor desconhecido: {kind}")
        with self._lock:
            token = next(self._ids)
            self._entries[token] = _Consumer(kind=kind, label=label or kind)
            return token

    def discard(self, token: int) -> None:
        with self._lock:
            self._entries.pop(token, None)

    def total(self) -> int:
        with self._lock:
            return len(self._entries)

    def counts(self) -> dict[str, int]:
        with self._lock:
            entries = list(self._entries.values())
        counts = dict.fromkeys(self.KINDS, 0)
        for entry in entries:
            counts[entry.kind] += 1
        counts["total"] = len(entries)
        return counts


def _open_rtsp(url: str) -> Any:
    """Abertura padrão, com OpenCV. Injetável para testar sem rede."""
    import cv2

    capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except cv2.error:  # pragma: no cover — depende do backend do FFmpeg
        pass
    return capture


class RtspReader:
    """Thread que mantém o slot alimentado com o quadro mais recente."""

    def __init__(
        self,
        *,
        url: Callable[[], str] | None = None,
        open_capture: Callable[[str], Any] = _open_rtsp,
        path_ready: Callable[[], bool | None] | None = None,
        consumers: Consumers | None = None,
        waiter: Callable[[float], Any] | None = None,
    ) -> None:
        self.slot = FrameSlot()
        self.consumers = consumers or Consumers()
        self._url = url or (lambda: settings.rtsp_url)
        self._open = open_capture
        probe = PathProbe(ttl=NO_PATH_POLL_S)
        self._path_ready = path_ready or (lambda: probe.ready(settings.flyhub_stream_path))

        self._stop = threading.Event()
        self._wait = waiter or self._stop.wait
        self._thread: threading.Thread | None = None

        self._lock = threading.Lock()
        self._capture_rate = RateMeter()
        self._seq = itertools.count(1)
        self._connected = False
        self._source: str | None = None
        self._error: str | None = None
        self._reconnects = 0
        self._retry_at: float | None = None
        self._session_started_at: float | None = None
        self._frames = 0
        self._resolution: tuple[int, int] | None = None
        self._change: tuple[ResolutionChange, float] | None = None

    # --- ciclo de vida --------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, name="video-reader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    # --- laço -----------------------------------------------------------------

    def run(self) -> None:
        capture = None
        backoff = RECONNECT_MIN_S
        idle_since: float | None = None
        waiting_for_path = False

        while not self._stop.is_set():
            if self.consumers.total() == 0:
                # Ninguém olhando e nenhuma coleta: não consome o RTSP.
                if capture is not None:
                    if idle_since is None:
                        idle_since = time.monotonic()
                    elif time.monotonic() - idle_since >= IDLE_CLOSE_S:
                        capture.release()
                        capture = None
                        self._on_disconnect(None)
                        log.info("video_ocioso_liberado")
                self._wait(IDLE_TICK_S)
                continue

            idle_since = None

            if capture is None:
                if self._path_ready() is False:
                    # Abrir aqui gastaria um FFmpeg por tentativa para receber o
                    # mesmo 404. Esperar custa uma leitura do cache do probe.
                    if not waiting_for_path:
                        waiting_for_path = True
                        self._on_disconnect(NO_PATH_MESSAGE)
                    backoff = RECONNECT_MIN_S
                    self._wait(NO_PATH_POLL_S)
                    continue
                waiting_for_path = False

                url = self._url()
                capture = self._open(url)
                if not capture.isOpened():
                    capture.release()
                    capture = None
                    self._on_disconnect(f"não foi possível abrir {url}")
                    backoff = self._wait_backoff(backoff)
                    continue
                self._on_connect(url)
                # O backoff NÃO é zerado aqui: só um quadro de verdade confirma
                # que a conexão serve para alguma coisa.

            ok, image = capture.read()
            if not ok or image is None:
                capture.release()
                capture = None
                self._on_disconnect("stream interrompido")
                backoff = self._wait_backoff(backoff)
                continue

            backoff = RECONNECT_MIN_S
            self._publish(image)

        if capture is not None:
            capture.release()

    def _wait_backoff(self, backoff: float) -> float:
        with self._lock:
            self._retry_at = time.monotonic() + backoff
        self._wait(backoff)
        with self._lock:
            self._retry_at = None
        return next_backoff(backoff)

    def _on_connect(self, url: str) -> None:
        with self._lock:
            self._connected = True
            self._source = url
            self._error = None
            self._session_started_at = time.monotonic()
            self._frames = 0
            # `_resolution` NÃO é zerada aqui, de propósito: trocar a qualidade
            # do canal no FlightHub derruba a sessão RTSP, e a resolução nova só
            # aparece na reconexão seguinte. Zerar apagaria o aviso justamente
            # no caso que ele existe para pegar.
        self._capture_rate.reset()
        log.info("video_conectado", source=url)

    def _on_disconnect(self, error: str | None) -> None:
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._error = error
            self._session_started_at = None
            if error and was_connected:
                self._reconnects += 1
        self._capture_rate.reset()
        self.slot.clear()
        if error and was_connected:
            log.warning("video_desconectado", error=error)

    def _publish(self, image: Any) -> None:
        now = time.monotonic()
        with self._lock:
            started = self._session_started_at or now
            self._frames += 1
            height, width = image.shape[:2]
            if self._resolution is None:
                self._resolution = (width, height)
            elif self._resolution != (width, height):
                previous = f"{self._resolution[0]}×{self._resolution[1]}"
                current = f"{width}×{height}"
                self._change = (ResolutionChange(previous, current, time.time()), now)
                self._resolution = (width, height)
                log.warning("video_resolucao_mudou", previous=previous, current=current)

        self._capture_rate.tick()
        self.slot.publish(
            Frame(
                image=image,
                seq=next(self._seq),
                captured_at=now,
                captured_epoch=time.time(),
                session_started_at=started,
            )
        )

    # --- estado ---------------------------------------------------------------

    @property
    def capture_fps(self) -> float:
        return self._capture_rate.value()

    def snapshot(self) -> VideoStats:
        """A metade da tabela CONEXÃO que o leitor conhece."""
        with self._lock:
            connected = self._connected
            source = self._source
            error = self._error
            retry_at = self._retry_at
            started = self._session_started_at
            resolution = self._resolution
            frames = self._frames
            change = self._change

        now = time.monotonic()
        if change and now - change[1] > RESOLUTION_WARNING_S:
            # Sem nova troca por 5 min, o problema passou: o aviso some sozinho.
            change = None
            with self._lock:
                self._change = None

        return VideoStats(
            connected=connected,
            source=source,
            error=error,
            retry_in_seconds=round(retry_at - now, 1) if retry_at else None,
            consumers=self.consumers.total(),
            capture_fps=self._capture_rate.value() if connected else None,
            dropped_frames=self.slot.dropped,
            frames=frames,
            uptime_seconds=int(now - started) if started else 0,
            resolution=f"{resolution[0]}×{resolution[1]}" if resolution else None,
            resolution_change=change[0] if change else None,
        )
