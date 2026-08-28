"""Contrato das rotas: forma da resposta e formato de erro."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_reports_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_dashboard_summary_has_the_four_cards(client):
    response = await client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"flight_connection", "inspection_count", "open_notes", "mape"}


async def test_unknown_dataset_returns_the_error_envelope(client):
    response = await client.get("/api/v1/datasets/9999")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert "não encontrado" in error["message"]


async def test_saving_without_an_active_collection_conflicts(client):
    response = await client.post("/api/v1/flight/collection/save")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COLLECTION_STATE"


async def test_flight_status_fills_the_connection_table(client, monkeypatch):
    """Com `FLIGHT_SOURCE=fake` a tabela CONEXÃO não fica só de travessão.

    A fonte é fixada aqui em vez de herdada do `.env`: numa máquina com
    `FLIGHT_SOURCE=real` e o MediaMTX no ar, o teste media o broker de verdade
    e falhava por falta de leitor de quadros — sem nada de errado no código.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "flight_source", "fake")

    response = await client.get("/api/v1/flight/status")
    assert response.status_code == 200

    metrics = response.json()["metrics"]
    assert metrics["resolution"] and metrics["capture_fps"]
    assert metrics["model_loaded"] is False  # sem pesos: passthrough
    assert metrics["resolution_change"] is None


async def test_the_preflight_lists_every_condition_with_its_fix(client):
    """O modal precisa dizer o que falta e o que fazer, não só que falhou."""
    response = await client.get("/api/v1/flight/collection/preflight")
    assert response.status_code == 200

    body = response.json()
    assert {item["key"] for item in body["checks"]} == {"stream", "mediamtx", "tunnel", "disk"}
    assert all(item["ok"] or item["fix"] for item in body["checks"])
    assert body["next_version"].startswith("v")
    assert body["defaults"]["interval_options"] == [0.5, 1.0, 2.0, 5.0]


async def test_the_credentials_endpoint_never_returns_a_key(client):
    response = await client.get("/api/v1/datasets/roboflow/credentials")
    assert response.status_code == 200
    assert response.json() == []

    schema = client._transport.app.openapi()["components"]["schemas"]["RoboflowCredentialOut"]
    assert "api_key" not in schema["properties"]
    assert not any("key" in name for name in schema["properties"])


async def test_endpoint_rejects_an_unsupported_scheme(client):
    response = await client.put("/api/v1/flight/endpoint", json={"endpoint": "ftp://x"})
    assert response.status_code == 422
