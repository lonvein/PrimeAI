"""Unit tests for the upgraded specialized construction detector."""

from pathlib import Path
import torch

from backend.app.schemas.contracts import MachineryType
from backend.app.services.detector import MACHINERY_ALIASES, MachineryDetector


def test_machinery_aliases_covers_all_8_dgp_classes() -> None:
    """Verify all 8 target DGP Moscow machinery types are represented in MACHINERY_ALIASES."""
    target_values = {
        "dump_truck",
        "excavator",
        "roller",
        "crane_manipulator",
        "bulldozer",
        "mobile_crane",
        "concrete_mixer",
        "truck",
    }
    mapped_values = set(MACHINERY_ALIASES.values())
    for target in target_values:
        assert target in mapped_values, f"Missing target class in aliases: {target}"
        # Ensure it maps to valid MachineryType enum
        assert MachineryType(target) is not None


def test_detector_loads_specialized_model() -> None:
    """Verify detector loads specialized construction weights and sets model_is_construction."""
    detector = MachineryDetector()
    assert detector.is_real_model is True
    assert detector.model_is_construction is True
    assert detector.imgsz == 640


def test_detector_inference_on_real_construction_photo() -> None:
    """Run inference on real photo (Screenshot_13.png) containing excavator/dozer."""
    photo_path = Path("data/raw_photos/Screenshot_13.png")
    assert photo_path.exists(), "Test photo data/raw_photos/Screenshot_13.png missing"

    detector = MachineryDetector()
    with open(photo_path, "rb") as f:
        detections = detector.detect(f.read())

    assert len(detections) > 0, "Expected at least 1 detection on construction photo"
    for det in detections:
        assert isinstance(det.class_name, MachineryType)
        assert 0.0 <= det.confidence <= 1.0
        assert len(det.bbox) == 4
        assert det.bbox[2] > det.bbox[0]
        assert det.bbox[3] > det.bbox[1]

    # Verify at least one specialized construction class was identified
    detected_classes = {d.class_name for d in detections}
    assert (
        MachineryType.EXCAVATOR in detected_classes
        or MachineryType.BULLDOZER in detected_classes
        or MachineryType.DUMP_TRUCK in detected_classes
    )


def test_vram_limit_under_2gb() -> None:
    """Verify that inference does not exceed the 2 GB VRAM limit."""
    if not torch.cuda.is_available():
        return  # Skip GPU VRAM test on CPU environment

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    detector = MachineryDetector()
    photo_path = Path("data/raw_photos/Screenshot_13.png")
    with open(photo_path, "rb") as f:
        img_bytes = f.read()

    # Run 4 inferences to simulate a batch
    for _ in range(4):
        detector.detect(img_bytes)

    peak_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
    # Must be under 2048 MB (2 GB)
    assert peak_mb < 2048.0, f"Peak VRAM ({peak_mb:.1f} MB) exceeded 2 GB limit!"
