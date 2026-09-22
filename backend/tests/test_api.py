"""Smoke tests for API routes."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Extended health check now reports model status.
    assert "model" in body
    assert body["model"] in ("real", "fallback")