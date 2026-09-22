"""Unit tests for plan-versus-fact rules.

Tests cover two scenarios:
1. model_is_construction=True  — fine-tuned model, full CRITICAL/OK/WARNING semantics.
2. model_is_construction=False — generic COCO model, absence → WARNING (not CRITICAL).
"""

from backend.app.schemas.contracts import IncidentStatus, ObservationQuality
from backend.app.services.matcher import evaluate_compliance


# ---------------------------------------------------------------------------
# Tests with construction-specific model (full strict semantics)
# ---------------------------------------------------------------------------


def test_missing_machinery_is_critical_with_construction_model() -> None:
    """When a fine-tuned model is used, missing required machinery → CRITICAL."""
    result = evaluate_compliance(
        "котлован",
        ["excavator"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.CRITICAL
    assert "dump_truck" in result.missing_machinery
    assert "bulldozer" in result.missing_machinery


def test_complete_excavation_machinery_is_ok() -> None:
    """All required machinery present → OK."""
    result = evaluate_compliance(
        "котлован",
        ["excavator", "dump_truck", "bulldozer"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.OK
    assert result.observation_quality is ObservationQuality.HIGH


def test_unexpected_machinery_is_warning() -> None:
    """Extra machinery on site → WARNING."""
    result = evaluate_compliance(
        "котлован",
        ["excavator", "dump_truck", "bulldozer", "roller"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.WARNING
    assert "roller" in result.unexpected_machinery


# ---------------------------------------------------------------------------
# Tests with generic COCO model (honest observation semantics)
# ---------------------------------------------------------------------------


def test_missing_machinery_is_warning_with_coco_model() -> None:
    """When using generic COCO model, missing classes → WARNING (not CRITICAL),
    because COCO cannot detect most construction equipment."""
    result = evaluate_compliance(
        "котлован",
        ["truck"],
        model_is_real=True,
        model_is_construction=False,
    )
    assert result.status is IncidentStatus.WARNING
    assert result.observation_quality is ObservationQuality.MEDIUM


def test_complete_set_is_ok_even_with_coco() -> None:
    """If all required machinery happens to be detected, OK regardless of model type."""
    result = evaluate_compliance(
        "котлован",
        ["excavator", "dump_truck", "bulldozer"],
        model_is_real=True,
        model_is_construction=False,
    )
    assert result.status is IncidentStatus.OK


# ---------------------------------------------------------------------------
# Tests with synthetic fallback (no model)
# ---------------------------------------------------------------------------


def test_synthetic_model_gives_warning() -> None:
    """When no model is loaded (synthetic fallback), always WARNING with LOW quality."""
    result = evaluate_compliance(
        "котлован",
        ["excavator"],
        model_is_real=False,
        model_is_construction=False,
    )
    assert result.status is IncidentStatus.WARNING
    assert result.observation_quality is ObservationQuality.LOW


# ---------------------------------------------------------------------------
# Tests for unknown stages
# ---------------------------------------------------------------------------


def test_unknown_stage_gives_warning() -> None:
    """Unknown stage name → WARNING: cannot validate."""
    result = evaluate_compliance(
        "Совершенно неизвестный этап",
        ["excavator", "dump_truck"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.WARNING
    assert "нормативном справочнике" in result.explanation.lower() or "не найден" in result.explanation


# ---------------------------------------------------------------------------
# Tests for all 5 stages in ontology
# ---------------------------------------------------------------------------


def test_foundation_stage_ok() -> None:
    result = evaluate_compliance(
        "Устройство фундамента / Сваи",
        ["mobile_crane", "concrete_mixer", "truck"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.OK


def test_landscaping_stage_ok() -> None:
    result = evaluate_compliance(
        "Благоустройство и дорожные работы",
        ["roller", "dump_truck", "crane_manipulator"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.OK


def test_empty_detections_coco() -> None:
    """Empty detection list with COCO model → WARNING (not CRITICAL)."""
    result = evaluate_compliance(
        "котлован",
        [],
        model_is_real=True,
        model_is_construction=False,
    )
    assert result.status is IncidentStatus.WARNING


def test_multiple_same_class() -> None:
    """Multiple detections of same class should count correctly."""
    # Котлован requires: excavator(1), dump_truck(1), bulldozer(1)
    # Providing 3 excavators but no dump_truck → still missing
    result = evaluate_compliance(
        "котлован",
        ["excavator", "excavator", "excavator"],
        model_is_real=True,
        model_is_construction=True,
    )
    assert result.status is IncidentStatus.CRITICAL
    assert "dump_truck" in result.missing_machinery
    assert "bulldozer" in result.missing_machinery
    assert "excavator" not in result.missing_machinery