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


def test_get_incident_pdf() -> None:
    """Verify PDF endpoint returns valid PDF file for an existing incident."""
    from backend.app.db.models import IncidentAlert
    from backend.app.db.session import SessionLocal

    # Insert a test incident
    db = SessionLocal()
    incident = IncidentAlert(
        stage_name="Земляные работы / Котлован",
        status="CRITICAL",
        explanation="Тестовое критическое нарушение для проверки PDF.",
        observation_quality="HIGH",
        missing_machinery='["dump_truck"]',
        unexpected_machinery='[]',
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    inc_id = incident.id
    db.close()

    # Test main endpoint
    response = client.get(f"/api/v1/monitoring/incidents/{inc_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert f'filename="incident_{inc_id}.pdf"' in response.headers["content-disposition"]

    # Test alias endpoint
    response_alias = client.get(f"/api/v1/incidents/{inc_id}/pdf")
    assert response_alias.status_code == 200
    assert response_alias.headers["content-type"] == "application/pdf"


def test_get_incident_pdf_not_found() -> None:
    """Non-existent incident should return 404."""
    response = client.get("/api/v1/monitoring/incidents/999999/pdf")
    assert response.status_code == 404