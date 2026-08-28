"""Regras do vídeo com inferência da tela Voo.

A integração sabe ler RTSP, inferir e codificar JPEG. Este service decide o que
disso vira resposta de API: o formato do multipart, e o retrato consolidado que
preenche a tabela CONEXÃO — vídeo e modelo juntos, numa estrutura só.

Lembrete de fronteira: **Dataset mostra a imagem original, Voo mostra a
processada.** O MJPEG daqui é o quadro depois da inferência e pertence só à
tela Voo. O quadro cru continua guardado em `Rendered.frame`, para a coleta.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.logging import get_logger
from app.integrations.vision import BOUNDARY, VideoStats, detector, video

log = get_logger(__name__)

MEDIA_TYPE = f"multipart/x-mixed-replace; boundary={BOUNDARY}"

# O MJPEG é uma resposta que nunca termina. Sem estes cabeçalhos, um proxy ou
# o próprio navegador acumula os quadros e o vídeo chega em blocos.
STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "X-Accel-Buffering": "no",
}


@dataclass(slots=True)
class VideoSnapshot:
    """Vídeo e modelo no mesmo instante."""

    stats: VideoStats
    model_loaded: bool
    model_version: str | None
    model_error: str | None


class VideoService:
    @staticmethod
    def frames() -> AsyncIterator[bytes]:
        """Fluxo multipart. Um consumidor por cliente; o RTSP fecha sozinho."""
        return video.mjpeg()

    @staticmethod
    async def snapshot() -> VideoSnapshot:
        """Retrato para a tela.

        `detector.poll()` pode carregar os pesos, que é lento — vai para uma
        thread. Ele existe porque, com o leitor ocioso, ninguém chama
        `detect()`: sem este polling a tela mostraria estado velho enquanto o
        operador copia o `best.pt` para a pasta.
        """
        status = await asyncio.to_thread(detector.poll)
        return VideoSnapshot(
            stats=video.stats(),
            model_loaded=bool(status["loaded"]),
            model_version=status["weights_name"] if status["loaded"] else None,
            model_error=status["error"],
        )

    @staticmethod
    def start() -> None:
        video.start()

    @staticmethod
    def stop() -> None:
        video.stop()
