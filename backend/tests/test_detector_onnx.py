"""Unit tests for the upgraded high-performance ONNX inference detector."""

from pathlib import Path
import numpy as np
import pytest

from backend.app.schemas.contracts import DetectionItem, MachineryType
from backend.app.services.detector import MACHINERY_ALIASES, LABEL_MAPPING_RU, MachineryDetector


def test_detector_initialization_onnx() -> None:
    """Verify detector correctly initializes with best.onnx and sets is_onnx=True."""
    onnx_path = Path("backend/models/best.onnx")
    if not onnx_path.exists():
        pytest.skip("backend/models/best.onnx not found on disk")

    detector = MachineryDetector(weights_path=onnx_path)
    assert detector.is_real_model is True
    assert detector.is_onnx is True
    assert detector.model_is_construction is True
    assert detector.imgsz == 640
    assert detector.device == "cpu"


def test_detector_inference_synthetic_zeros() -> None:
    """Run synthetic zero image through detect() to verify non-exceptional execution."""
    detector = MachineryDetector()
    zeros = np.zeros((640, 640, 3), dtype=np.uint8)

    detections = detector.detect(zeros)
    assert isinstance(detections, list)
    assert len(detections) == 0


def test_detector_inference_schema_conformance() -> None:
    """Verify that detections strictly adhere to the Pydantic DetectionItem contract."""
    photo_path = Path("data/raw_photos/Screenshot_13.png")
    if not photo_path.exists():
        pytest.skip("data/raw_photos/Screenshot_13.png not found")

    detector = MachineryDetector()
    detections = detector.detect(photo_path)

    assert isinstance(detections, list)
    assert len(detections) > 0

    for det in detections:
        assert isinstance(det, DetectionItem)
        assert isinstance(det.class_name, MachineryType)
        assert isinstance(det.confidence, float)
        assert 0.0 <= det.confidence <= 1.0
        assert isinstance(det.bbox, list)
        assert len(det.bbox) == 4
        x1, y1, x2, y2 = det.bbox
        assert x2 >= x1
        assert y2 >= y1


def test_detector_flexible_input_types() -> None:
    """Verify detect() accepts bytes, string path, Path object, and numpy array."""
    photo_path = Path("data/raw_photos/Screenshot_13.png")
    if not photo_path.exists():
        pytest.skip("data/raw_photos/Screenshot_13.png not found")

    detector = MachineryDetector()

    # 1. Path object
    dets_path_obj = detector.detect(photo_path)
    # 2. String path
    dets_str_path = detector.detect(str(photo_path))
    # 3. Bytes
    with open(photo_path, "rb") as f:
        dets_bytes = detector.detect(f.read())
    # 4. Numpy array
    import cv2
    img_bgr = cv2.imread(str(photo_path))
    dets_numpy = detector.detect(img_bgr)

    assert len(dets_path_obj) == len(dets_str_path) == len(dets_bytes) == len(dets_numpy)
    assert len(dets_path_obj) > 0


def test_detector_fallback_to_pt_when_onnx_missing() -> None:
    """Verify detector logs warning and falls back to .pt when an ONNX model is missing."""
    pt_path = Path("backend/models/best.pt")
    if not pt_path.exists():
        pytest.skip("backend/models/best.pt not found on disk")

    detector = MachineryDetector(weights_path="backend/models/non_existent_weights.onnx")
    assert detector.is_real_model is True
    assert detector.is_onnx is False
    assert detector.weights_path == pt_path
