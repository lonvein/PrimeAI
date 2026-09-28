"""Unit tests for Cyrillic image annotation and Russian localization mapping."""

from pathlib import Path
import numpy as np
import pytest

from backend.app.schemas.contracts import DetectionItem, MachineryType
from backend.app.services.detector import LABEL_MAPPING_RU, annotate_image
from backend.app.api.v1.monitoring import _annotate_and_save
from backend.app.core.config import get_settings


def test_label_mapping_ru_covers_all_dgp_classes() -> None:
    """Ensure all normative DGP Moscow machinery classes have Russian translations."""
    required_classes = [
        "dump_truck",
        "excavator",
        "roller",
        "manipulator",
        "crane_manipulator",
        "bulldozer",
        "mobile_crane",
        "concrete_mixer",
        "truck",
    ]
    for cls in required_classes:
        assert cls in LABEL_MAPPING_RU, f"Missing {cls} in LABEL_MAPPING_RU"
        ru_label = LABEL_MAPPING_RU[cls]
        assert isinstance(ru_label, str)
        assert len(ru_label) > 0
        # Ensure it contains Cyrillic characters
        assert any("\u0400" <= char <= "\u04FF" for char in ru_label)


def test_annotate_image_renders_cyrillic_without_error() -> None:
    """Verify annotate_image draws boxes and Cyrillic text onto a NumPy BGR image."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = [
        DetectionItem(
            class_name=MachineryType.EXCAVATOR,
            confidence=0.88,
            bbox=[50.0, 50.0, 200.0, 200.0],
        ),
        DetectionItem(
            class_name=MachineryType.DUMP_TRUCK,
            confidence=0.92,
            bbox=[250.0, 100.0, 450.0, 300.0],
        ),
        DetectionItem(
            class_name=MachineryType.BULLDOZER,
            confidence=0.75,
            bbox=[10.0, 320.0, 150.0, 460.0],
        ),
    ]

    annotated = annotate_image(img, detections)

    assert isinstance(annotated, np.ndarray)
    assert annotated.shape == (480, 640, 3)
    assert annotated.dtype == np.uint8
    # Pixels should have been drawn (not all zeros anymore)
    assert np.any(annotated > 0)


def test_annotate_image_empty_detections() -> None:
    """Verify annotate_image with empty detections returns image unchanged."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    res = annotate_image(img, [])
    assert res.shape == (100, 100, 3)
    assert np.all(res == 0)


def test_annotate_image_handles_edge_boundaries() -> None:
    """Verify annotate_image handles boxes near the edges of the image (y1 near 0, out of bounds)."""
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    detections = [
        DetectionItem(
            class_name=MachineryType.MOBILE_CRANE,
            confidence=0.95,
            bbox=[0.0, 0.0, 199.0, 199.0],  # covers entire image, y1=0
        ),
        DetectionItem(
            class_name=MachineryType.CONCRETE_MIXER,
            confidence=0.65,
            bbox=[-10.0, -10.0, 250.0, 250.0],  # out of bounds coords
        ),
    ]
    annotated = annotate_image(img, detections)
    assert annotated.shape == (200, 200, 3)
    assert np.any(annotated > 0)


def test_annotate_and_save_saves_file_and_returns_valid_url(tmp_path: Path) -> None:
    """Verify _annotate_and_save writes the annotated photo to disk and returns URL."""
    settings = get_settings()
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    detections = [
        DetectionItem(
            class_name=MachineryType.ROLLER,
            confidence=0.81,
            bbox=[30.0, 30.0, 150.0, 150.0],
        )
    ]
    file_uuid = "test_annotation_uuid_123"

    saved_path, url = _annotate_and_save(img, detections, file_uuid)

    assert saved_path.exists()
    assert saved_path.is_file()
    assert url == f"/static/annotated/{file_uuid}.jpg"

    # Cleanup
    if saved_path.exists():
        saved_path.unlink()
    debug_path = settings.debug_dir / f"{file_uuid}.jpg"
    if debug_path.exists():
        debug_path.unlink()
