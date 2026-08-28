"""O modelo do ponto de vista da aplicação: toggle, persistência e peso ruim.

O que estes testes protegem é a promessa do fluxo de entrega: quem treina copia
um arquivo e mais nada. Isso só se sustenta se ligar/desligar for barato, se a
escolha do operador sobreviver a um reinício e se um `.pt` inválido não tirar a
plataforma do ar.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.integrations.vision.detector import Detector
from app.services.app_settings_service import MODEL_INFERENCE_ENABLED, AppSettingsService
from app.services.model_service import ModelService

# Sem `pytestmark` de módulo: metade dos testes aqui é síncrona (o detector é
# uma peça de thread, não de laço de eventos) e a marca de módulo aplicada a
# função síncrona vira aviso do pytest-asyncio.
asyncio_test = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def restore_shared_detector():
    """O detector é único no processo, e o toggle mexe nele.

    Sem esta restauração um teste que desliga a inferência deixaria os
    seguintes rodando com o modelo desligado — e a suíte passaria ou falharia
    conforme a ordem, que é o pior tipo de teste quebrado.
    """
    from app.integrations.vision import detector

    before = detector.enabled
    yield
    detector.set_enabled(before)


def frame() -> np.ndarray:
    return np.zeros((6, 8, 3), dtype=np.uint8)


NAMES = {0: "corrosão"}


class _FakeModel:
    """Um YOLO de mentira: conta as chamadas e não devolve detecção nenhuma."""

    def __init__(self) -> None:
        self.names = dict(NAMES)
        self.calls = 0

    def predict(self, *_args, **_kwargs):
        self.calls += 1
        return []


def _loaded(tmp_path) -> tuple[Detector, _FakeModel]:
    """Detector com pesos "carregados", sem passar por ultralytics nem torch."""
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"nao-e-um-modelo-de-verdade")
    detector = Detector(weights=weights)
    model = _FakeModel()
    detector._model = model
    detector._names = dict(NAMES)
    detector._mtime = weights.stat().st_mtime
    return detector, model


# --- toggle -------------------------------------------------------------------


def test_disabling_stops_inference_without_unloading_the_weights(tmp_path):
    """Desligar e recarregar são ações distintas — esta é a diferença.

    Se desligar descarregasse, religar pagaria de novo os segundos de carga e
    comparar detecção ligada e desligada no mesmo voo deixaria de ser viável.
    """
    detector, model = _loaded(tmp_path)

    detector.detect(frame())
    assert model.calls == 1

    detector.set_enabled(False)
    detector.detect(frame())

    assert model.calls == 1  # não inferiu
    assert detector.is_loaded is True  # mas os pesos continuam em memória
    assert detector.is_active is False
    assert detector.status()["mode"] == "passthrough"

    detector.set_enabled(True)
    detector.detect(frame())
    assert model.calls == 2  # religou sem recarregar nada


def test_the_frame_comes_out_untouched_while_disabled(tmp_path):
    detector, _ = _loaded(tmp_path)
    detector.set_enabled(False)

    original = frame()
    returned, detections = detector.detect(original)

    assert returned is original
    assert detections == []


@asyncio_test
async def test_the_toggle_survives_a_restart(session):
    """Reiniciar o backend não pode religar o que o operador desligou."""
    await ModelService(session).toggle(False)

    # Um processo novo: instância nova de detector, mesmo banco.
    from app.integrations.vision import detector as shared

    shared.set_enabled(True)  # o padrão de quem acaba de subir
    await ModelService(session).restore()

    assert shared.enabled is False
    assert await AppSettingsService(session).get(MODEL_INFERENCE_ENABLED) == "false"


@asyncio_test
async def test_toggle_and_reload_are_separate_endpoints(client):
    """Uma tela que só tivesse "recarregar" não permitiria o teste A/B do voo."""
    off = await client.post("/api/v1/model/toggle", json={"enabled": False})
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    assert off.json()["active"] is False

    reloaded = await client.post("/api/v1/model/reload")
    assert reloaded.status_code == 200
    # Recarregar não religa: quem liga é o toggle.
    assert reloaded.json()["enabled"] is False

    on = await client.post("/api/v1/model/toggle", json={"enabled": True})
    assert on.json()["enabled"] is True


# --- peso inválido ------------------------------------------------------------


def test_a_corrupt_weights_file_falls_back_to_passthrough(tmp_path, monkeypatch):
    """Peso ruim não derruba a plataforma: o vídeo continua, o erro aparece."""
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"isto nao e um checkpoint")

    class _Boom:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("invalid load key")

    import app.integrations.vision.detector as module

    fake = type(module)("ultralytics")
    fake.YOLO = _Boom
    monkeypatch.setitem(__import__("sys").modules, "ultralytics", fake)

    detector = Detector(weights=weights)
    _, detections = detector.detect(frame())  # não levanta

    assert detections == []
    assert detector.is_loaded is False
    status = detector.status()
    assert "invalid load key" in status["error"]
    assert status["mode"] == "passthrough"


@asyncio_test
async def test_the_state_endpoint_explains_the_absence_of_weights(client):
    """Sem pesos não é erro — mas a tela nunca fica em silêncio sobre isso."""
    response = await client.get("/api/v1/model")

    assert response.status_code == 200
    body = response.json()
    assert body["loaded"] is False
    assert body["error"] is None
    assert body["message"]  # sempre há uma frase para o operador


# --- métricas do treino -------------------------------------------------------


@asyncio_test
async def test_metrics_from_the_training_land_in_the_database(session, tmp_path):
    """`metrics.json` vira linha em `model_metrics`, sem duplicar na segunda vez."""
    status = {
        "weights_name": "best.pt",
        "metrics": {
            "generated_at_iso": "2026-08-20T10:00:00+00:00",
            "weights": {"sha256": "a" * 64},
            "metrics": {"map50": 0.812, "map50_95": 0.604, "precision": 0.79, "recall": 0.74},
        },
    }
    service = ModelService(session)

    assert await service.sync_metrics(status) is True
    assert await service.sync_metrics(status) is False  # idempotente

    from sqlalchemy import select

    from app.models.inspection import ModelMetric

    rows = (await session.execute(select(ModelMetric))).scalars().all()
    assert {row.metric for row in rows} == {"map50", "map50_95", "precision", "recall"}
    assert all(row.model_version == f"best@{'a' * 12}" for row in rows)


@asyncio_test
async def test_missing_metrics_are_not_an_error(session):
    """Um best.pt copiado à mão, sem métricas, tem que funcionar igual."""
    assert await ModelService(session).sync_metrics({"weights_name": "best.pt"}) is False
