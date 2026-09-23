"""Unit tests for multi-photo batch compliance aggregation."""

from backend.app.schemas.contracts import IncidentStatus, ObservationQuality
from backend.app.services.matcher import evaluate_batch_compliance


def test_batch_compliance_resolves_partial_observability() -> None:
    """If camera 1 sees excavator and camera 2 sees dump_truck and bulldozer,
    together all 3 required machines for 'котлован' are present -> OK!"""
    stage_name = "Земляные работы / Котлован"
    # camera 1 detected excavator
    cam1_dets = ["excavator"]
    # camera 2 detected dump_truck and bulldozer
    cam2_dets = ["dump_truck", "bulldozer"]

    all_dets = cam1_dets + cam2_dets

    status, explanation, quality, missing, unexpected, summary = evaluate_batch_compliance(
        stage_name=stage_name,
        all_detected_classes=all_dets,
        total_images=2,
        model_is_real=True,
        model_is_construction=True,
    )

    assert status == IncidentStatus.OK
    assert missing == []
    assert quality == ObservationQuality.HIGH
    assert summary["excavator"] == 1
    assert summary["dump_truck"] == 1
    assert summary["bulldozer"] == 1
    assert "100% соответствие" in explanation


def test_batch_compliance_critical_when_still_missing() -> None:
    """Across 3 cameras, excavator is still missing with construction model -> CRITICAL."""
    stage_name = "Земляные работы / Котлован"
    # 3 cameras only saw dump_truck and bulldozer
    all_dets = ["dump_truck", "bulldozer", "dump_truck"]

    status, explanation, quality, missing, unexpected, summary = evaluate_batch_compliance(
        stage_name=stage_name,
        all_detected_classes=all_dets,
        total_images=3,
        model_is_real=True,
        model_is_construction=True,
    )

    assert status == IncidentStatus.CRITICAL
    assert "excavator" in missing
    assert "дефицит техники" in explanation


def test_batch_compliance_coco_model_warning() -> None:
    """With generic COCO model, missing machinery gives WARNING."""
    stage_name = "Земляные работы / Котлован"
    all_dets = ["truck"]

    status, explanation, quality, missing, unexpected, summary = evaluate_batch_compliance(
        stage_name=stage_name,
        all_detected_classes=all_dets,
        total_images=2,
        model_is_real=True,
        model_is_construction=False,
    )

    assert status == IncidentStatus.WARNING
    assert "excavator" in missing
