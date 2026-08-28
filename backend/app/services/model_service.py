"""O modelo de visão do ponto de vista da aplicação.

A divisão de responsabilidade que este arquivo existe para sustentar: quem
treina copia dois arquivos para `models/` e não faz mais nada. Sem reiniciar,
sem endpoint, sem comando. Se algum passo exigisse mexer na aplicação, o
desenho estaria errado — ver `models/README.md`.

Três peças, com fronteiras distintas:

* **`Detector`** (integração) sabe carregar pesos, inferir e reler o arquivo
  quando o mtime muda. Não conhece banco nem SSE, e roda em thread.
* **`ModelService`** (aqui) traduz esse estado para a tela, persiste o toggle e
  grava as métricas do treino em `model_metrics`.
* **`watch()`** (aqui) é o vigia: sem ele, o estado só mudaria quando alguém
  pedisse a tela. Com o leitor ocioso ninguém chama `detect()`, e a promessa
  "copie o arquivo e em segundos o badge muda" não se sustentaria.

Toggle e reload são **ações distintas**. `toggle` liga e desliga a inferência
mantendo os pesos em memória; `reload` relê o disco. Juntá-las impediria
comparar detecção ligada e desligada no mesmo voo, que é justamente o teste que
se faz ao receber um modelo novo.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import bus
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.integrations.vision import detector
from app.models.enums import DataSource
from app.models.inspection import ModelMetric
from app.schemas.model import ClassMetric, ModelState, TrainingMetrics
from app.services.app_settings_service import MODEL_INFERENCE_ENABLED, AppSettingsService

log = get_logger(__name__)

WATCH_INTERVAL_S = 2.0
"""Ritmo do vigia. O `Detector` já limita o `stat()` a um por segundo, então
descer disto não acelera nada — só acorda o laço de eventos à toa."""

METRIC_KEYS = ("map50", "map50_95", "precision", "recall")


class ModelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = AppSettingsService(session)

    # --- leitura --------------------------------------------------------------

    async def state(self) -> ModelState:
        """Estado atual. Pode carregar os pesos, então vai para uma thread."""
        status = await asyncio.to_thread(detector.poll)
        return _to_state(status)

    # --- ações ----------------------------------------------------------------

    async def toggle(self, enabled: bool) -> ModelState:
        """Liga ou desliga a inferência e **persiste** a escolha.

        A persistência não é detalhe: reiniciar o backend não pode religar
        sozinho um modelo que o operador desligou de propósito. Por isso o
        estado mora em `app_settings`, e não numa variável de processo.
        """
        await self._settings.set_bool(MODEL_INFERENCE_ENABLED, enabled)
        status = detector.set_enabled(enabled)
        await bus.publish("model.changed", enabled=enabled, loaded=bool(status["loaded"]))
        log.info("model_toggle", enabled=enabled, loaded=bool(status["loaded"]))
        return _to_state(status)

    async def reload(self) -> ModelState:
        """Relê o disco agora, sem esperar o mtime mudar.

        Existe para o caso em que o arquivo é reescrito com o mesmo mtime —
        raro, mas acontece com algumas ferramentas de cópia. Não mexe no
        toggle.
        """
        status = await asyncio.to_thread(detector.reload)
        await self.sync_metrics(status)
        await bus.publish(
            "model.changed",
            enabled=bool(status["enabled"]),
            loaded=bool(status["loaded"]),
        )
        log.info(
            "model_reload",
            loaded=bool(status["loaded"]),
            weights=status["weights_path"],
            error=status["error"],
        )
        return _to_state(status)

    async def restore(self) -> None:
        """Aplica ao detector o toggle gravado. Chamado uma vez, no start."""
        enabled = await self._settings.get_bool(MODEL_INFERENCE_ENABLED, default=True)
        detector.set_enabled(enabled)
        log.info("model_toggle_restaurado", enabled=enabled)

    # --- métricas do treino ---------------------------------------------------

    async def sync_metrics(self, status: dict[str, Any]) -> bool:
        """Grava em `model_metrics` o que o `metrics.json` traz. Devolve se gravou.

        Idempotente pela versão: copiar o mesmo par de arquivos duas vezes não
        duplica linha. A versão é o hash dos pesos quando o notebook o
        escreveu — o mtime muda a cada cópia, o conteúdo não —, e cai no nome
        do arquivo mais a data do treino quando não há hash.

        Métrica de treino **não** é `mape`: o card do Dashboard continua lendo
        a série que a equipe de inspeção publica, e as duas convivem na mesma
        tabela sem se sobrepor.
        """
        metrics = status.get("metrics")
        if not isinstance(metrics, dict):
            return False
        values = metrics.get("metrics")
        if not isinstance(values, dict):
            return False

        version = _model_version(status, metrics)
        already = await self._session.scalar(
            select(ModelMetric.id).where(ModelMetric.model_version == version).limit(1)
        )
        if already:
            return False

        measured_at = _parse_trained_at(metrics) or datetime.now(UTC)
        written = 0
        for key in METRIC_KEYS:
            value = values.get(key)
            if not isinstance(value, int | float):
                continue
            # O "atual" é por métrica: um treino novo não pode deixar duas
            # linhas de map50 marcadas como vigentes ao mesmo tempo.
            for row in (
                await self._session.execute(
                    select(ModelMetric).where(
                        ModelMetric.metric == key, ModelMetric.is_current.is_(True)
                    )
                )
            ).scalars():
                row.is_current = False
            self._session.add(
                ModelMetric(
                    model_version=version,
                    metric=key,
                    value=float(value),
                    measured_at=measured_at,
                    is_current=True,
                    source=DataSource.COLLECTED,
                )
            )
            written += 1

        if not written:
            return False
        await self._session.commit()
        log.info("model_metrics_gravadas", model_version=version, metricas=written)
        return True


# --- tradução -----------------------------------------------------------------


def _model_version(status: dict[str, Any], metrics: dict[str, Any]) -> str:
    """Identidade do treino, estável entre cópias do mesmo arquivo."""
    stem = str(status.get("weights_name") or "best.pt").rsplit(".", 1)[0]
    weights = metrics.get("weights")
    sha = weights.get("sha256") if isinstance(weights, dict) else None
    if isinstance(sha, str) and sha:
        return f"{stem}@{sha[:12]}"
    trained = _parse_trained_at(metrics)
    return f"{stem}@{trained:%Y%m%d-%H%M%S}" if trained else stem


def _parse_trained_at(metrics: dict[str, Any]) -> datetime | None:
    raw = metrics.get("generated_at_iso")
    if isinstance(raw, str):
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(raw)
    epoch = metrics.get("generated_at")
    if isinstance(epoch, int | float):
        with contextlib.suppress(OSError, OverflowError, ValueError):
            return datetime.fromtimestamp(epoch, UTC)
    return None


def _to_metrics(status: dict[str, Any]) -> TrainingMetrics | None:
    document = status.get("metrics")
    if not isinstance(document, dict):
        return None
    values = document.get("metrics") if isinstance(document.get("metrics"), dict) else {}
    training = document.get("training") if isinstance(document.get("training"), dict) else {}
    dataset = document.get("dataset") if isinstance(document.get("dataset"), dict) else {}
    weights = document.get("weights") if isinstance(document.get("weights"), dict) else {}
    per_class = document.get("per_class") if isinstance(document.get("per_class"), list) else []

    return TrainingMetrics(
        map50=_number(values.get("map50")),
        map50_95=_number(values.get("map50_95")),
        precision=_number(values.get("precision")),
        recall=_number(values.get("recall")),
        classes=[str(item) for item in document.get("classes") or []],
        per_class=[
            ClassMetric(
                name=str(item.get("name", "?")),
                map50=_number(item.get("map50")),
                map50_95=_number(item.get("map50_95")),
                precision=_number(item.get("precision")),
                recall=_number(item.get("recall")),
            )
            for item in per_class
            if isinstance(item, dict)
        ],
        trained_at=_parse_trained_at(document),
        base_model=_text(training.get("base_model")),
        epochs=training.get("epochs") if isinstance(training.get("epochs"), int) else None,
        dataset=_text(dataset.get("name")),
        weights_sha256=_text(weights.get("sha256")),
        split_check_ok=(
            dataset.get("split_check_ok")
            if isinstance(dataset.get("split_check_ok"), bool)
            else None
        ),
    )


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _text(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _message(status: dict[str, Any]) -> str:
    """A frase que a tela mostra. Os quatro estados, nenhum deles silêncio."""
    if status["error"]:
        return (
            f"Os pesos existem mas não carregaram: {status['error']} "
            "O vídeo continua passando cru."
        )
    if not status["loaded"]:
        return (
            f"Nenhum arquivo de pesos em {status['weights_path']}. "
            "Copie best.pt para lá e o badge muda sozinho, sem reiniciar."
        )
    if not status["enabled"]:
        return (
            "Pesos carregados e inferência desligada — o vídeo passa cru de propósito. "
            "Religar volta a detectar no quadro seguinte, sem recarregar nada."
        )
    return f"Inferindo com {status['weights_name']} · {len(status['classes'])} classe(s)."


def _to_state(status: dict[str, Any]) -> ModelState:
    return ModelState(
        loaded=bool(status["loaded"]),
        enabled=bool(status["enabled"]),
        active=bool(status["active"]),
        weights_path=str(status["weights_path"]),
        weights_name=str(status["weights_name"]),
        weights_exists=bool(status["weights_exists"]),
        classes=list(status["classes"]),
        conf=float(status["conf"]),
        loaded_at=(
            datetime.fromtimestamp(status["loaded_at"], UTC) if status["loaded_at"] else None
        ),
        error=status["error"],
        metrics=_to_metrics(status),
        metrics_error=status["metrics_error"],
        message=_message(status),
    )


# --- vigia --------------------------------------------------------------------


async def watch(interval: float = WATCH_INTERVAL_S) -> None:
    """Percebe o arquivo novo e conta para o resto do sistema.

    Sem este laço a promessa do fluxo de entrega não se cumpriria: o hot-reload
    do `Detector` acontece dentro de `detect()`, e com ninguém assistindo ao
    vídeo `detect()` não é chamado. A pessoa copiaria o `best.pt` e a tela
    continuaria dizendo "sem modelo" até alguém abrir o stream.

    Roda para sempre; cancelado no desligamento. Toda exceção é engolida e
    registrada de propósito: o vigia é acessório, e derrubá-lo não pode
    derrubar a aplicação — nem ele mesmo, no laço seguinte.
    """
    seen = -1
    while True:
        try:
            status = await asyncio.to_thread(detector.poll)
            generation = int(status["generation"])
            if generation != seen:
                first = seen == -1
                seen = generation
                async with SessionLocal() as session:
                    await ModelService(session).sync_metrics(status)
                # O primeiro laço só fotografa o estado inicial: anunciar
                # "mudou" no start faria toda tela recém-aberta piscar.
                if not first:
                    await bus.publish(
                        "model.changed",
                        enabled=bool(status["enabled"]),
                        loaded=bool(status["loaded"]),
                    )
                    log.info(
                        "model_changed",
                        weights=status["weights_path"],
                        loaded=bool(status["loaded"]),
                        enabled=bool(status["enabled"]),
                        treinado_em=_iso(_to_metrics(status)),
                        classes=status["classes"],
                        error=status["error"],
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover — o vigia nunca derruba nada
            log.warning("model_watch_falhou", error=f"{type(exc).__name__}: {exc}")
        await asyncio.sleep(interval)


def _iso(metrics: TrainingMetrics | None) -> str | None:
    return metrics.trained_at.isoformat() if metrics and metrics.trained_at else None
