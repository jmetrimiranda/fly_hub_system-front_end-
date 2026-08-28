"""Detector de objetos com dois modos: com pesos e sem pesos.

Portado de `app/inference.py` do M4TD. O princípio é o mesmo e não se negocia:
**o modelo é opcional**. No começo do projeto não existem pesos — o objetivo da
coleta é justamente criar o dataset para treinar o primeiro. Sem arquivo,
`detect()` devolve o quadro intacto e nenhuma detecção; não levanta e não
impede a aplicação de subir.

Três estados, todos visíveis em `status()`:

| `loaded` | `error` | Significado                                  |
| --- | --- | --- |
| `True`  | `None` | inferindo de verdade                          |
| `False` | `None` | não há arquivo de pesos — estado inicial      |
| `False` | texto  | havia pesos, mas a carga falhou               |

Ver vídeo cru achando que são detecções reais é pior que não ver nada, por isso
a tela sempre diz em qual dos três está.

`ultralytics` é importado **dentro** de `_load()`, nunca no topo do módulo: ele
arrasta torch (~2,5 GB) e a aplicação precisa subir em máquina sem ele.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# Um stat() por segundo é barato; um por quadro, a 30 fps, não é.
MTIME_CHECK_EVERY_S = 1.0

BOX_COLOR = (80, 200, 120)  # BGR
LABEL_TEXT = (14, 20, 16)


@dataclass(frozen=True, slots=True)
class Detection:
    name: str
    conf: float
    box: tuple[int, int, int, int]
    """x1, y1, x2, y2 em pixels."""


class Detector:
    """Carrega pesos sob demanda e recarrega quando o arquivo muda."""

    def __init__(self, weights: str | Path | None = None, conf: float | None = None) -> None:
        self.weights_path = Path(weights) if weights else settings.weights_path
        self._conf = settings.model_conf if conf is None else conf
        self._lock = threading.Lock()
        self._model: Any = None
        self._names: dict[int, str] = {}
        self._error: str | None = None
        self._loaded_at: float | None = None
        # -1.0 é impossível como mtime real, então a primeira checagem carrega.
        self._mtime: float | None = -1.0
        self._checked_at = 0.0

    # --- estado ---------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def classes(self) -> list[str]:
        return [self._names[key] for key in sorted(self._names)]

    @property
    def version(self) -> str | None:
        """Nome que a interface exibe no badge. `None` em passthrough."""
        return self.weights_path.stem if self.is_loaded else None

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self.is_loaded,
            "weights_path": str(self.weights_path),
            "weights_name": self.weights_path.name,
            "weights_exists": self.weights_path.is_file(),
            "classes": self.classes,
            "conf": self._conf,
            "error": self._error,
            "loaded_at": self._loaded_at,
            "mode": "inferência" if self.is_loaded else "passthrough",
        }

    # --- carga ----------------------------------------------------------------

    def _weights_mtime(self) -> float | None:
        try:
            return self.weights_path.stat().st_mtime
        except OSError:
            return None

    def _maybe_reload(self) -> None:
        """Recarrega se o arquivo apareceu, sumiu ou mudou. Nunca a cada quadro."""
        now = time.monotonic()
        if now - self._checked_at < MTIME_CHECK_EVERY_S:
            return
        self._checked_at = now
        mtime = self._weights_mtime()
        if mtime != self._mtime:
            self._load(mtime)

    def _load(self, mtime: float | None, force: bool = False) -> None:
        with self._lock:
            if not force and mtime == self._mtime:
                return  # outra thread carregou enquanto esta esperava o lock
            self._mtime = mtime
            self._loaded_at = None

            if mtime is None:
                # Ausência de pesos não é erro: é o ponto de partida do projeto.
                self._model, self._names, self._error = None, {}, None
                return

            try:
                from ultralytics import YOLO  # import preguiçoso: arrasta torch
            except Exception as exc:  # qualquer falha aqui vira passthrough
                self._model, self._names = None, {}
                self._error = f"ultralytics indisponível ({type(exc).__name__}: {exc})"[:200]
                log.warning("detector_sem_ultralytics", weights=str(self.weights_path))
                return

            try:
                model = YOLO(str(self.weights_path))
                names = getattr(model, "names", {}) or {}
                self._names = {int(k): str(v) for k, v in dict(names).items()}
                self._model = model
                self._error = None
                self._loaded_at = time.time()
                log.info("detector_carregado", weights=str(self.weights_path), classes=self.classes)
            except Exception as exc:  # pesos ruins não derrubam o vídeo
                self._model, self._names = None, {}
                self._error = f"falha ao carregar pesos ({type(exc).__name__}: {exc})"[:200]
                log.warning("detector_falhou", error=self._error)

    def reload(self) -> dict[str, Any]:
        """Força nova tentativa agora, sem esperar o mtime mudar."""
        self._checked_at = time.monotonic()
        self._load(self._weights_mtime(), force=True)
        return self.status()

    def poll(self) -> dict[str, Any]:
        """Checa o arquivo e devolve o estado.

        O hot-reload por mtime acontece dentro de `detect()`, e com o leitor
        ocioso ninguém chama `detect()` — a tela mostraria estado velho
        enquanto o operador copia o `best.pt` para a pasta. Pode carregar o
        modelo, que é lento: chame fora do laço de eventos.
        """
        self._maybe_reload()
        return self.status()

    # --- inferência -----------------------------------------------------------

    def detect(self, frame: Any) -> tuple[Any, list[Detection]]:
        """Devolve (quadro, detecções). Em passthrough, o quadro sai intacto."""
        self._maybe_reload()
        model = self._model
        if model is None:
            return frame, []

        try:
            results = model.predict(frame, conf=self._conf, verbose=False)
        except Exception as exc:  # o vídeo continua; o operador vê o badge mudar
            with self._lock:
                self._model = None
                self._error = f"inferência falhou ({type(exc).__name__}: {exc})"[:200]
            log.warning("detector_inferencia_falhou", error=self._error)
            return frame, []

        return frame, self._parse(results)

    def _parse(self, results: Any) -> list[Detection]:
        found: list[Detection] = []
        for result in results or []:
            for box in getattr(result, "boxes", None) or []:
                try:
                    x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    class_id = int(box.cls[0])
                except (IndexError, TypeError, ValueError):
                    continue
                found.append(
                    Detection(self._names.get(class_id, str(class_id)), conf, (x1, y1, x2, y2))
                )
        return found

    @staticmethod
    def draw(frame: Any, detections: list[Detection]) -> Any:
        """Desenha as caixas no quadro recebido — modifica no lugar.

        Quem chama sempre passa uma cópia: o quadro cru é o que a coleta grava,
        e Dataset mostra imagem original enquanto Voo mostra a processada.
        """
        for detection in detections:
            x1, y1, x2, y2 = detection.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
            label = f"{detection.name} {detection.conf:.2f}"
            (width, height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            top = max(y1 - height - 6, 0)
            cv2.rectangle(frame, (x1, top), (x1 + width + 8, top + height + 6), BOX_COLOR, -1)
            cv2.putText(
                frame,
                label,
                (x1 + 4, top + height + 1),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                LABEL_TEXT,
                1,
                cv2.LINE_AA,
            )
        return frame


detector = Detector()
"""Instância única do processo. O leitor e o painel falam com esta."""
