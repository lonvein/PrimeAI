"""Unit tests for smart camera angle evaluation (ObservationQuality) and safe compliance matching."""

from backend.app.schemas.contracts import DetectionItem, IncidentStatus, MachineryType, ObservationQuality
from backend.app.services.matcher import evaluate_compliance


def test_observation_quality_low_for_distant_camera_view() -> None:
    """When detected boxes have relative area < 0.02 (e.g. 20th floor camera >80m away),

    quality must be LOW, status must be downgraded to WARNING, and DGP recommendation provided.
    """
    # Image frame: 1920 x 1080 -> Area = 2,073,600
    # Tiny box: 100 x 100 -> Area = 10,000 -> Area_rel = 10,000 / 2,073,600 = ~0.0048 (< 0.02)
    small_detection = DetectionItem(
        class_name=MachineryType.EXCAVATOR,
        confidence=0.75,
        bbox=[500.0, 500.0, 600.0, 600.0],
    )

    response = evaluate_compliance(
        "Земляные работы / Котлован",  # requires excavator, dump_truck, bulldozer
        [MachineryType.EXCAVATOR.value],
        detections=[small_detection],
        image_shape=(1080, 1920),
        model_is_real=True,
        model_is_construction=True,
    )

    # 1. Observation quality must be LOW
    assert response.observation_quality == ObservationQuality.LOW

    # 2. Status must NOT be CRITICAL (safeguard against false penalties due to camera angle)
    assert response.status == IncidentStatus.WARNING

    # 3. Camera recommendation must be present
    assert response.camera_recommendation is not None
    assert "LOW" in response.camera_recommendation
    assert "ракурс" in response.camera_recommendation.casefold() or "угол" in response.camera_recommendation.casefold()


def test_observation_quality_high_for_normal_camera_view() -> None:
    """When detected boxes have relative area >= 0.02, quality is HIGH."""
    # Image frame: 1000 x 1000 -> Area = 1,000,000
    # Box: 300 x 300 -> Area = 90,000 -> Area_rel = 0.09 (>= 0.02)
    normal_detection = DetectionItem(
        class_name=MachineryType.EXCAVATOR,
        confidence=0.88,
        bbox=[200.0, 200.0, 500.0, 500.0],
    )

    response = evaluate_compliance(
        "Подготовка территории / Демонтаж",
        [MachineryType.EXCAVATOR.value, MachineryType.DUMP_TRUCK.value],
        detections=[normal_detection],
        image_shape=(1000, 1000),
        model_is_real=True,
        model_is_construction=True,
    )

    assert response.observation_quality == ObservationQuality.HIGH
    assert response.status == IncidentStatus.OK
    assert response.camera_recommendation is None
