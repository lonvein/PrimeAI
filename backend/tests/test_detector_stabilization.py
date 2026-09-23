"""Unit tests for detector stabilization and nested bounding box suppression."""

from backend.app.schemas.contracts import DetectionItem, MachineryType
from backend.app.services.detector import MachineryDetector, suppress_contained_boxes


def test_suppress_contained_boxes_filters_nested_box() -> None:
    """When a smaller box (e.g. boom) is >75% contained inside a larger box, it is suppressed."""
    large_box = DetectionItem(
        class_name=MachineryType.EXCAVATOR,
        confidence=0.85,
        bbox=[100.0, 100.0, 500.0, 500.0],  # Area: 400 * 400 = 160,000
    )
    nested_box = DetectionItem(
        class_name=MachineryType.EXCAVATOR,
        confidence=0.45,
        bbox=[150.0, 150.0, 300.0, 300.0],  # Area: 150 * 150 = 22,500; 100% inside large_box
    )

    detections = [large_box, nested_box]
    filtered = suppress_contained_boxes(detections, threshold=0.75)

    assert len(filtered) == 1
    assert filtered[0].confidence == 0.85
    assert filtered[0].bbox == large_box.bbox


def test_suppress_contained_boxes_keeps_adjacent_separate_boxes() -> None:
    """Distinct adjacent boxes (e.g. excavator next to dump truck) must NOT be suppressed."""
    box1 = DetectionItem(
        class_name=MachineryType.EXCAVATOR,
        confidence=0.85,
        bbox=[100.0, 100.0, 300.0, 300.0],
    )
    box2 = DetectionItem(
        class_name=MachineryType.DUMP_TRUCK,
        confidence=0.80,
        bbox=[320.0, 100.0, 520.0, 300.0],  # No overlap
    )

    detections = [box1, box2]
    filtered = suppress_contained_boxes(detections, threshold=0.75)

    assert len(filtered) == 2


def test_detector_inference_parameters() -> None:
    """Verify detector parameters comply with hackathon stabilization requirements."""
    detector = MachineryDetector()
    assert detector.confidence == 0.35, "Confidence threshold must be 0.35"
    assert detector.iou == 0.45, "IoU threshold must be 0.45"
    assert detector.imgsz == 640, "Input image size must be 640"
