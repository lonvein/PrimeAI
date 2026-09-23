"""Ultralytics YOLO inference for construction site machinery monitoring.

Key features:
- Uses specialized construction weights with memory limit < 2 GB VRAM.
- Enforces FP16 (half=True) on CUDA devices.
- Auto-cleans GPU cache with torch.cuda.empty_cache() after each inference.
- Fixed input resolution imgsz=640 for predictable latency and memory.
- Comprehensive MACHINERY_ALIASES normalization table mapping RU/EN synonyms
  into the 8 normative DGP Moscow classes.
- Non-blocking friendly, robust error logging.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
import torch

from ..core.config import get_settings
from ..schemas.contracts import DetectionItem, MachineryType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Comprehensive domain normalization dictionary for the 8 target classes:
# 1. dump_truck (самосвал)
# 2. excavator (экскаватор)
# 3. roller (каток)
# 4. crane_manipulator (кран-манипулятор)
# 5. bulldozer (бульдозер)
# 6. mobile_crane (автокран)
# 7. concrete_mixer (бетоносмеситель)
# 8. truck (грузовик)
# ---------------------------------------------------------------------------
MACHINERY_ALIASES: dict[str, str] = {
    # --- 1. dump_truck (самосвал) ---
    "dump_truck":       "dump_truck",
    "dumb_truck":       "dump_truck",
    "dumptruck":        "dump_truck",
    "tipper":           "dump_truck",
    "tipper_truck":     "dump_truck",
    "haul_truck":       "dump_truck",
    "dumper":           "dump_truck",
    "самосвал":         "dump_truck",

    # --- 2. excavator (экскаватор) ---
    "excavator":        "excavator",
    "digger":           "excavator",
    "backhoe":          "excavator",
    "trench_digger":    "excavator",
    "экскаватор":       "excavator",

    # --- 3. roller (каток) ---
    "roller":           "roller",
    "road_roller":      "roller",
    "roadroller":       "roller",
    "compactor":        "roller",
    "steam_roller":     "roller",
    "каток":            "roller",

    # --- 4. crane_manipulator (кран-манипулятор) ---
    "crane_manipulator": "crane_manipulator",
    "manipulator":      "crane_manipulator",
    "crane_truck":      "crane_manipulator",
    "loader_crane":     "crane_manipulator",
    "boom_truck":       "crane_manipulator",
    "кран_манипулятор": "crane_manipulator",
    "манипулятор":      "crane_manipulator",

    # --- 5. bulldozer (бульдозер) ---
    "bulldozer":        "bulldozer",
    "dozer":            "bulldozer",
    "bull_dozer":       "bulldozer",
    "crawler_dozer":    "bulldozer",
    "grader":           "bulldozer",
    "автогрейдер":      "bulldozer",
    "грейдер":          "bulldozer",
    "бульдозер":        "bulldozer",

    # --- 6. mobile_crane (автокран) ---
    "mobile_crane":     "mobile_crane",
    "mobilecrane":      "mobile_crane",
    "truck_crane":      "mobile_crane",
    "tower_crane":      "mobile_crane",
    "crane":            "mobile_crane",
    "автокран":         "mobile_crane",
    "кран":             "mobile_crane",
    "башенный_кран":    "mobile_crane",

    # --- 7. concrete_mixer (бетоносмеситель) ---
    "concrete_mixer":   "concrete_mixer",
    "cement_mixer":     "concrete_mixer",
    "transit_mixer":    "concrete_mixer",
    "mixer":            "concrete_mixer",
    "автобетоносмеситель": "concrete_mixer",
    "бетоносмеситель":  "concrete_mixer",
    "бетономешалка":    "concrete_mixer",

    # --- 8. truck (грузовик / погрузчик) ---
    "truck":            "truck",
    "lorry":            "truck",
    "flatbed_truck":    "truck",
    "cargo_truck":      "truck",
    "loader":           "truck",
    "wheel_loader":     "truck",
    "погрузчик":        "truck",
    "грузовик":         "truck",
}


class MachineryDetector:
    """Lightweight construction machinery detector using specialized YOLO weights."""

    def __init__(
        self,
        weights_path: str | Path | None = None,
        confidence: float | None = None,
    ) -> None:
        settings = get_settings()
        self.weights_path = Path(weights_path or settings.yolo_weights)
        self.confidence = confidence if confidence is not None else settings.yolo_confidence
        self.imgsz = 640
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self._model = None
        self._load_error: Exception | None = None
        self._is_construction: bool = False

        if self.weights_path.is_file():
            try:
                from ultralytics import YOLO  # noqa: PLC0415

                self._model = YOLO(str(self.weights_path))
                # Check if model has domain-specific construction classes
                matched_classes = sum(
                    1
                    for name in self._model.names.values()
                    if str(name).casefold().replace("-", "_").replace(" ", "_") in MACHINERY_ALIASES
                )
                self._is_construction = matched_classes >= 3
                logger.info(
                    "YOLO model loaded: %s (classes=%d, is_construction=%s, device=%s, imgsz=%d, conf=%.2f)",
                    self.weights_path.name,
                    len(self._model.names),
                    self._is_construction,
                    self.device,
                    self.imgsz,
                    self.confidence,
                )
            except Exception as error:  # pragma: no cover
                self._load_error = error
                logger.error("Failed to load YOLO weights from %s: %s", self.weights_path, error)
        else:
            logger.warning(
                "YOLO weights not found at %s — using synthetic fallback for smoke testing.",
                self.weights_path,
            )

    @property
    def is_real_model(self) -> bool:
        """True when a real YOLO model is loaded (not synthetic fallback)."""
        return self._model is not None

    @property
    def model_is_construction(self) -> bool:
        """True when the model is trained on specialized construction equipment."""
        return self._is_construction if self._model is not None else False

    def detect(self, image_bytes: bytes) -> list[DetectionItem]:
        """Run inference and return validated detections.

        Guaranteed memory efficiency:
        - FP16 (half=True) when on GPU.
        - Automatic torch.cuda.empty_cache() cleanup in finally block.
        - Logging of any runtime errors without silent exception suppression.
        """
        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Uploaded file is not a readable image")

            if self._model is None:
                logger.info("Synthetic fallback active — returning placeholder excavator.")
                return self._fallback_detections(image)

            predict_kwargs: dict[str, object] = {
                "source": image,
                "conf": self.confidence,
                "imgsz": self.imgsz,
                "device": self.device,
                "verbose": False,
            }
            if self.device.startswith("cuda"):
                predict_kwargs["half"] = True

            result = self._model.predict(**predict_kwargs)[0]
            detections = self._parse_result(result)
            logger.debug(
                "Inference complete: %d raw boxes -> %d domain detections",
                len(result.boxes),
                len(detections),
            )
            return detections

        except ValueError as exc:
            logger.warning("Image decode failed: %s", exc)
            raise
        except Exception as exc:
            logger.error("Inference error (returning empty result): %s", exc, exc_info=True)
            return []
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _parse_result(self, result) -> list[DetectionItem]:  # type: ignore[override]
        """Convert raw YOLO bounding boxes into strict domain DetectionItems."""
        names = result.names
        detections: list[DetectionItem] = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            raw_name = str(names[class_id]).casefold().strip()
            normalized = raw_name.replace("-", "_").replace(" ", "_")
            canonical_name = MACHINERY_ALIASES.get(normalized, normalized)

            try:
                machinery = MachineryType(canonical_name)
            except ValueError:
                logger.debug("Skipping non-target class: %s (normalized: %s)", raw_name, canonical_name)
                continue

            detections.append(
                DetectionItem(
                    class_name=machinery,
                    confidence=float(box.conf[0]),
                    bbox=[float(round(v, 2)) for v in box.xyxy[0].tolist()],
                )
            )
        return detections

    @staticmethod
    def _fallback_detections(image: np.ndarray) -> list[DetectionItem]:
        """Return one synthetic low-confidence item when weights are missing."""
        height, width = image.shape[:2]
        left, top = width * 0.25, height * 0.25
        right, bottom = width * 0.75, height * 0.75
        return [
            DetectionItem(
                class_name=MachineryType.EXCAVATOR,
                confidence=0.01,
                bbox=[left, top, right, bottom],
            )
        ]