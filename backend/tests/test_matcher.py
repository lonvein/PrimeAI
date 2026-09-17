"""Unit tests for plan-versus-fact rules."""

from backend.app.schemas.contracts import IncidentStatus
from backend.app.services.matcher import evaluate_compliance


def test_missing_excavation_machinery_is_critical() -> None:
    result = evaluate_compliance("котлован", ["excavator"])
    assert result.status is IncidentStatus.CRITICAL
    assert "dump_truck" in result.missing_machinery


def test_complete_excavation_machinery_is_ok() -> None:
    result = evaluate_compliance("котлован", ["excavator", "dump_truck", "bulldozer"])
    assert result.status is IncidentStatus.OK


def test_unexpected_machinery_is_warning() -> None:
    result = evaluate_compliance("котлован", ["excavator", "dump_truck", "bulldozer", "roller"])
    assert result.status is IncidentStatus.WARNING
    assert "roller" in result.unexpected_machinery