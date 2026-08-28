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

Sobre esses três estados existe um eixo independente: `enabled`. Ele liga e
desliga a **inferência**, sem descarregar os pesos. São ações distintas de
propósito — juntá-las impediria comparar detecção ligada e desligada no mesmo
voo, que é exatamente o teste que se faz ao receber um modelo novo, e cada
alternância pagaria de novo o custo de carregar o modelo.

Ao lado dos pesos, `metrics.json`: o que o treino mediu. É lido junto e
recarregado sozinho quando muda, porque na prática os dois arquivos são
copiados em sequência e o segundo costuma chegar depois do primeiro.

`ultralytics` é importado **dentro** de `_load()`, nunca no topo do módulo: ele
arrasta torch (~2,5 GB) e a aplicação precisa subir em máquina sem ele.
"""

from __future__ import annotations

import json
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

METRICS_NAME = "metrics.json"


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
        self._metrics_mtime: float | None = -1.0
        self._metrics: dict[str, Any] | None = None
        self._metrics_error: str | None = None
        self._checked_at = 0.0
        # Inferência ligada. Quem manda de verdade é o banco: o estado escolhido
        # pelo operador é restaurado no start (ver `services/model_service.py`).
        self._enabled = True
        # Sobe a cada mudança observável de estado. É o que permite ao vigia
        # perceber "isto mudou" sem comparar dicionário com dicionário.
        self._generation = 0

    # --- estado ---------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Há pesos carregados em memória. Independe de a inferência estar ligada."""
        return self._model is not None

    @property
    def is_active(self) -> bool:
        """Vai realmente inferir no próximo quadro."""
        return self._model is not None and self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> dict[str, Any]:
        """Liga ou desliga a inferência. **Não** descarrega os pesos.

        Desligar mantém o modelo em memória: religar volta a inferir no quadro
        seguinte, sem os segundos de carga. É a diferença entre este método e
        `reload()`, e é o que torna possível alternar durante um voo para
        comparar com e sem detecção.
        """
        with self._lock:
            if self._enabled == value:
                return self.status()
            self._enabled = value
            self._generation += 1
        log.info("detector_toggle", enabled=value, loaded=self.is_loaded)
        return self.status()

    @property
    def generation(self) -> int:
        """Contador de mudanças de estado. Ver `services/model_service.py`."""
        return self._generation

    @property
    def metrics(self) -> dict[str, Any] | None:
        """O `metrics.json` do treino, cru. `None` quando não existe."""
        return self._metrics

    @property
    def metrics_path(self) -> Path:
        return self.weights_path.parent / METRICS_NAME

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
            "enabled": self._enabled,
            "active": self.is_active,
            "generation": self._generation,
            "weights_path": str(self.weights_path),
            "weights_name": self.weights_path.name,
            "weights_exists": self.weights_path.is_file(),
            "weights_mtime": self._mtime if self._mtime and self._mtime > 0 else None,
            "classes": self.classes,
            "conf": self._conf,
            "error": self._error,
            "loaded_at": self._loaded_at,
            "metrics": self._metrics,
            "metrics_path": str(self.metrics_path),
            "metrics_error": self._metrics_error,
            "mode": "inferência" if self.is_active else "passthrough",
        }

    # --- carga ----------------------------------------------------------------

    def _weights_mtime(self) -> float | None:
        try:
            return self.weights_path.stat().st_mtime
        except OSError:
            return None

    def _metrics_file_mtime(self) -> float | None:
        try:
            return self.metrics_path.stat().st_mtime
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
            return
        # Os dois arquivos são copiados em sequência, e o `metrics.json` quase
        # sempre chega depois do `best.pt`. Sem esta segunda checagem a tela
        # ficaria com o modelo novo e as métricas do treino anterior até o
        # próximo reinício.
        metrics_mtime = self._metrics_file_mtime()
        if metrics_mtime != self._metrics_mtime:
            with self._lock:
                self._load_metrics(metrics_mtime)
                self._generation += 1

    def _load_metrics(self, mtime: float | None) -> None:
        """Lê `metrics.json` ao lado dos pesos. Chamar com o lock tomado.

        Métrica ausente ou ilegível **não** é erro de modelo: o `best.pt` pode
        ter sido copiado à mão, sem passar pelo notebook. O modelo carrega e
        infere igual; a tela apenas não mostra mAP.
        """
        self._metrics_mtime = mtime
        if mtime is None:
            self._metrics, self._metrics_error = None, None
            return
        try:
            document = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._metrics = None
            self._metrics_error = f"{type(exc).__name__}: {exc}"[:200]
            log.warning("detector_metrics_ilegivel", path=str(self.metrics_path), error=exc)
            return
        if not isinstance(document, dict):
            self._metrics = None
            self._metrics_error = "o metrics.json não contém um objeto JSON"
            return
        self._metrics, self._metrics_error = document, None

    def _load(self, mtime: float | None, force: bool = False) -> None:
        with self._lock:
            if not force and mtime == self._mtime:
                return  # outra thread carregou enquanto esta esperava o lock
            self._mtime = mtime
            self._loaded_at = None
            self._generation += 1
            self._load_metrics(self._metrics_file_mtime())

            if mtime is None:
                # Ausência de pesos não é erro: é o ponto de partida do projeto.
                self._model, self._names, self._error = None, {}, None
                log.info("detector_sem_pesos", weights=str(self.weights_path))
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
                log.info(
                    "detector_carregado",
                    weights=str(self.weights_path),
                    treinado_em=self._trained_at_label(),
                    classes=self.classes,
                    metricas=str(self.metrics_path) if self._metrics else None,
                )
            except Exception as exc:  # pesos ruins não derrubam o vídeo
                self._model, self._names = None, {}
                self._error = f"falha ao carregar pesos ({type(exc).__name__}: {exc})"[:200]
                log.warning("detector_falhou", error=self._error)

    def _trained_at_label(self) -> str | None:
        """Data do treino, como o `metrics.json` a escreveu. Só para o log."""
        metrics = self._metrics or {}
        value = metrics.get("generated_at_iso") or metrics.get("generated_at")
        return str(value) if value else None

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
        # Desligado é passthrough com os pesos **ainda em memória**: religar
        # volta a inferir no quadro seguinte, sem pagar a carga de novo.
        if not self._enabled:
            return frame, []
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
