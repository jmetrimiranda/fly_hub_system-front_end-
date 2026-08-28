"""Inferência sobre o quadro e saída MJPEG.

Segundo estágio do arranjo descrito em `reader.py`:

```text
leitor ──► slot ──► worker (thread) ──► slot ──► N clientes
                    detect + overlay   de 1     GET /flight/stream
                    + imencode         JPEG
```

A inferência roda **uma vez por quadro, não uma vez por cliente**: dois
navegadores abertos não dobram o custo, os dois leem do mesmo slot de saída.

O gerador MJPEG não encerra quando não há sinal — emite um quadro sintético com
o motivo, a ~1 fps. Encerrar o multipart deixaria um ícone quebrado na tela e
obrigaria o navegador a reconectar; assim, quando o stream volta, a imagem
volta sozinha na mesma conexão.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

from .detector import Detection, Detector, detector
from .metrics import RateMeter, VideoStats
from .reader import Consumers, Frame, FrameSlot, RtspReader

log = get_logger(__name__)

BOUNDARY = "frame"
WORKER_TICK_S = 0.5
PLACEHOLDER_SIZE = (360, 640)
HUD_HEIGHT = 26
FAKE_RESOLUTION = "960×720"

_PROCESS_STARTED_AT = time.monotonic()


@dataclass(slots=True)
class Rendered:
    """O que sai do worker: o JPEG anotado e o quadro cru que o gerou.

    O quadro cru fica preservado: a sobreposição existe só para o operador
    olhar, e é a imagem original que a coleta grava.
    """

    jpeg: bytes
    frame: Frame
    detections: list[Detection] = field(default_factory=list)
    latency_ms: float = 0.0


def fake_stats() -> VideoStats:
    """Números plausíveis para `FLIGHT_SOURCE=fake`.

    Mesma razão do `FAKE_PROBE` em `integrations/flyhub/client.py`: sem broker
    não há o que medir, e uma tabela inteira de travessões faria parecer que a
    tela está quebrada. São os valores que o M4TD reportava publicando de
    verdade — a tela diz `SEM MODELO — vídeo cru` do mesmo jeito.
    """
    return VideoStats(
        connected=True,
        source="simulado",
        capture_fps=30.0,
        inference_fps=30.0,
        latency_ms=12,
        uptime_seconds=int(time.monotonic() - _PROCESS_STARTED_AT),
        resolution=FAKE_RESOLUTION,
    )


class VideoStream:
    """Leitor, worker e saída MJPEG — um por processo."""

    def __init__(self, reader: RtspReader | None = None, model: Detector | None = None) -> None:
        self._reader = reader or RtspReader()
        self._detector = model or detector
        self._out = FrameSlot()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

        self._lock = threading.Lock()
        self._infer_rate = RateMeter()
        self._latency_ms = 0.0
        self._placeholder: tuple[str, bytes] | None = None

    @property
    def consumers(self) -> Consumers:
        return self._reader.consumers

    # --- ciclo de vida --------------------------------------------------------

    def start(self) -> None:
        """Sobe as threads. Elas ficam ociosas até alguém pedir vídeo."""
        if not settings.video_enabled:
            log.info("video_desligado", motivo="FLIGHT_SOURCE=fake")
            return
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._reader.start()
        self._worker = threading.Thread(target=self._run, name="video-worker", daemon=True)
        self._worker.start()
        log.info("video_iniciado", source=settings.rtsp_url)

    def stop(self) -> None:
        self._stop.set()
        self._reader.stop()
        if self._worker:
            self._worker.join(timeout=3)
        self._worker = None

    # --- worker ---------------------------------------------------------------

    def _run(self) -> None:
        last_seq = 0
        while not self._stop.is_set():
            if self.consumers.total() == 0:
                self._stop.wait(WORKER_TICK_S)
                continue

            item = self._reader.slot.take(last_seq, WORKER_TICK_S)
            if item is None:
                continue
            frame, last_seq = item

            _, detections = self._detector.detect(frame.image)

            annotated = frame.image.copy()
            self._detector.draw(annotated, detections)
            self._hud(annotated, frame, len(detections))

            ok, buffer = cv2.imencode(
                ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), settings.jpeg_quality]
            )
            if not ok:
                continue

            latency_ms = (time.monotonic() - frame.captured_at) * 1000
            with self._lock:
                self._latency_ms = latency_ms
            self._infer_rate.tick()
            self._out.publish(
                Rendered(
                    jpeg=buffer.tobytes(),
                    frame=frame,
                    detections=detections,
                    latency_ms=latency_ms,
                )
            )

    def _hud(self, image: Any, frame: Frame, detections: int) -> None:
        """Faixa preta no topo: FPS, resolução, contador e o modo do modelo.

        Três textos, não dois: "sem modelo" e "modelo desligado" parecem a
        mesma coisa no vídeo — quadro cru, nenhuma caixa — e são causas
        opostas. Quem grava a tela para revisar depois precisa saber qual dos
        dois estava valendo.
        """
        width, height = frame.size
        active = self._detector.is_active
        if active:
            mode = "modelo ativo"
        elif self._detector.is_loaded:
            mode = "modelo desligado"
        else:
            mode = "sem modelo"
        left = f"{self._reader.capture_fps:.1f} fps  {width}×{height}  #{frame.seq}"
        right = f"{mode}  {detections} det" if active else mode

        cv2.rectangle(image, (0, 0), (width, HUD_HEIGHT), (0, 0, 0), -1)
        cv2.putText(
            image, left, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 237, 243), 1, cv2.LINE_AA
        )
        (text_width, _), _ = cv2.getTextSize(right, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        color = (80, 200, 120) if active else (34, 153, 210)
        cv2.putText(
            image,
            right,
            (max(width - text_width - 8, 8), 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    # --- quadro sintético -----------------------------------------------------

    @staticmethod
    def _wrap(text: str, max_width: int, scale: float) -> list[str]:
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            (width, _), _ = cv2.getTextSize(candidate, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
            if width > max_width and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines[:3]

    def _waiting_frame(self) -> bytes:
        snapshot = self._reader.snapshot()
        if not settings.video_enabled:
            detail = "fonte de voo simulada (FLIGHT_SOURCE=fake) — não há stream para exibir"
        else:
            detail = snapshot.error or "nenhum quadro recebido ainda"
            if snapshot.retry_in_seconds:
                detail += f" — nova tentativa em {snapshot.retry_in_seconds:.0f} s"

        if self._placeholder and self._placeholder[0] == detail:
            return self._placeholder[1]

        height, width = PLACEHOLDER_SIZE
        canvas = np.full((height, width, 3), 18, dtype=np.uint8)
        cv2.putText(
            canvas,
            "Aguardando stream",
            (40, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (230, 237, 243),
            2,
            cv2.LINE_AA,
        )
        for index, line in enumerate(self._wrap(detail, width - 80, 0.5)):
            cv2.putText(
                canvas,
                line,
                (40, 186 + index * 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (139, 148, 158),
                1,
                cv2.LINE_AA,
            )
        ok, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        data = buffer.tobytes() if ok else b""
        self._placeholder = (detail, data)
        return data

    # --- saída ----------------------------------------------------------------

    def latest(self) -> Rendered | None:
        """Último quadro renderizado, com a sobreposição. É o que a tela Voo vê."""
        return self._out.peek()

    def raw_frame(self) -> Frame | None:
        """Último quadro **original**, direto do leitor e antes do detector.

        É daqui que a coleta grava. Ler de `latest()` pegaria a imagem já
        anotada e contaminaria o dataset com a saída do modelo anterior — a
        fronteira que o projeto inteiro depende de não cruzar.

        `peek` não consome: a coleta olhar o slot não tira o quadro do worker
        de inferência.
        """
        return self._reader.slot.peek()

    async def mjpeg(self) -> AsyncIterator[bytes]:
        """Gerador `multipart/x-mixed-replace`. Um consumidor por cliente.

        `take` bloqueia numa `Condition`, então roda em thread: dentro do laço
        de eventos ele seguraria todas as outras requisições da aplicação.
        """
        self.start()
        token = self.consumers.add("mjpeg")
        last_seq = 0
        try:
            while not self._stop.is_set():
                item = await asyncio.to_thread(self._out.take, last_seq, 1.0)
                if item is None:
                    jpeg = await asyncio.to_thread(self._waiting_frame)  # timeout => ~1 fps
                else:
                    rendered, last_seq = item
                    jpeg = rendered.jpeg
                yield (
                    b"--"
                    + BOUNDARY.encode()
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
        finally:
            self.consumers.discard(token)

    # --- estado ---------------------------------------------------------------

    def stats(self) -> VideoStats:
        """Tabela CONEXÃO completa: o que o leitor mede mais o que o worker mede."""
        if not settings.video_enabled:
            return fake_stats()

        stats = self._reader.snapshot()
        rendered = self._out.peek()
        with self._lock:
            latency = self._latency_ms
        if stats.connected:
            stats.inference_fps = self._infer_rate.value()
            stats.latency_ms = round(latency) if latency else None
        stats.detections = len(rendered.detections) if rendered else 0
        return stats


video = VideoStream()
"""Instância única do processo."""
