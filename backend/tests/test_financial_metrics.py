"""Unit and integration tests for financial metrics, early stage completion, and PDF generation."""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.schemas.contracts import IncidentStatus
from backend.app.services.matcher import evaluate_compliance
from backend.app.db.models import Stage, IncidentAlert
from backend.app.db.session import SessionLocal

client = TestClient(app)


def test_financial_metrics_calculation_critical() -> None:
    """Verify CRITICAL defect calculates delay_days = 2 * missing and penalty = delay * 350,000."""
    res = evaluate_compliance(
        stage_name="Снос строений и расчистка пятна застройки",
        detected_classes=["excavator", "excavator"],  # 2 excavators present, dump_truck missing
        model_is_real=True,
        model_is_construction=True,
    )
    assert res.status == IncidentStatus.CRITICAL
    assert "dump_truck" in res.missing_machinery
    # 1 missing type -> max(1, 1 * 2) = 2 days
    assert res.delay_days == 2
    # 2 * 350,000 = 700,000 RUB
    assert res.penalty_rub == 700000
    assert res.is_stage_completed is False


def test_financial_metrics_calculation_warning() -> None:
    """Verify WARNING calculates delay_days = 1 and penalty = 50,000."""
    res = evaluate_compliance(
        stage_name="Снос строений и расчистка пятна застройки",
        detected_classes=["excavator", "excavator", "dump_truck", "dump_truck", "dump_truck", "dump_truck", "roller"],
        # roller is unexpected
        model_is_real=True,
        model_is_construction=True,
    )
    assert res.status == IncidentStatus.WARNING
    assert res.delay_days == 1
    assert res.penalty_rub == 50000


def test_financial_metrics_calculation_ok() -> None:
    """Verify OK calculates delay_days = 0 and penalty = 0."""
    res = evaluate_compliance(
        stage_name="Снос строений и расчистка пятна застройки",
        detected_classes=["excavator", "excavator", "dump_truck", "dump_truck", "dump_truck", "dump_truck"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert res.status == IncidentStatus.OK
    assert res.delay_days == 0
    assert res.penalty_rub == 0


def test_early_stage_completion_lifts_requirements() -> None:
    """Verify when is_completed=True, compliance status is forced to OK with 0 penalty."""
    res = evaluate_compliance(
        stage_name="Снос строений и расчистка пятна застройки",
        detected_classes=[],  # zero machinery on site
        model_is_real=True,
        model_is_construction=True,
        is_completed=True,
        stage_id=1,
    )
    assert res.status == IncidentStatus.OK
    assert res.delay_days == 0
    assert res.penalty_rub == 0
    assert res.is_stage_completed is True
    assert "КС-2" in res.explanation
    assert res.missing_machinery == []


def test_toggle_stage_completed_api() -> None:
    """Verify PATCH /api/v1/schedule/stages/{stage_id}/toggle-completed flips is_completed in DB."""
    with SessionLocal() as db:
        stage = db.query(Stage).first()
        if not stage:
            stage = Stage(name="Тестовый этап для переключения", is_completed=False)
            db.add(stage)
            db.commit()
            db.refresh(stage)
        stage_id = stage.id
        initial_status = stage.is_completed

    response = client.patch(f"/api/v1/schedule/stages/{stage_id}/toggle-completed")
    assert response.status_code == 200
    data = response.json()
    assert data["stage_id"] == stage_id
    assert data["is_completed"] == (not initial_status)

    # Toggle back to original state to prevent test contamination
    response2 = client.patch(f"/api/v1/schedule/stages/{stage_id}/toggle-completed")
    assert response2.status_code == 200
    assert response2.json()["is_completed"] == initial_status


def test_get_incident_pdf_download() -> None:
    """Verify GET /api/v1/monitoring/incidents/{incident_id}/pdf returns PDF with akt_dgp filename."""
    # Create test incident in DB
    with SessionLocal() as db:
        incident = IncidentAlert(
            stage_name="Разработка грунта котлована с погрузкой",
            status="CRITICAL",
            explanation="Дефицит самосвалов",
            observation_quality="HIGH",
            missing_machinery='["dump_truck"]',
            unexpected_machinery="[]",
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)
        inc_id = incident.id

    response = client.get(f"/api/v1/monitoring/incidents/{inc_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert f'filename="akt_dgp_{inc_id}.pdf"' in response.headers["content-disposition"]
    assert len(response.content) > 1000
    # PDF magic header
    assert response.content[:4] == b"%PDF"
