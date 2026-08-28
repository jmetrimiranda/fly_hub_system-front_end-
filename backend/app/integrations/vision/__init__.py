"""Visão: leitura do RTSP, detecção e saída MJPEG.

Fica em `integrations/` e não em `services/` porque conversa com coisa externa
— o servidor RTSP e os pesos do modelo — e não contém regra de negócio. Quem
decide o que a tela mostra é `services/video_service.py`.

Esta plataforma **consome** o resultado do modelo; treinar é de outra equipe.
"""

from .detector import Detection, Detector, detector
from .metrics import RateMeter, ResolutionChange, VideoStats
from .reader import Consumers, Frame, RtspReader, next_backoff
from .stream import BOUNDARY, VideoStream, video

__all__ = [
    "BOUNDARY",
    "Consumers",
    "Detection",
    "Detector",
    "Frame",
    "RateMeter",
    "ResolutionChange",
    "RtspReader",
    "VideoStats",
    "VideoStream",
    "detector",
    "next_backoff",
    "video",
]
