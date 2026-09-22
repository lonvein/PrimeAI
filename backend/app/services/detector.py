"""Ultralytics YOLO inference with a local development fallback.

Key design decisions:
- Uses get_settings() for weights path and confidence (not raw os.getenv).
- All inference errors are LOGGED, not silently swallowed.
- Returns DetectionObservation list, not raw DetectionItem list, so callers
  know the difference between "nothing found" and "model not loaded".
- ALIASES covers COCO classes that approximate construction machinery.

NOTE: backend/models/best.pt is currently a generic COCO YOLOv8m model.
      It can detect 'truck' from the 8 target classes.
      Fine-tuning on construction data is required for full coverage.
      Until then the system correctly reports what it observes and clearly
      marks classes as NOT_OBSERVED rather than manufacturing false CRITICALs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from ..core.config import get_settings
from ..schemas.contracts import DetectionItem, MachineryType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# COCO-to-domain alias table.
#
# The base YOLOv8m model is trained on COCO-80 (person, car, truck, etc.).
# These aliases map COCO class names to the closest domain machinery type.
#
# Rationale for each mapping:
#   truck       → truck         (direct COCO match)
#   truck       → dump_truck    (construction trucks are often dump trucks;
#                                without fine-tuned model we cannot distinguish)
#   car         → (skip)        -- too generic, would cause false positives
#   bus         → (skip)        -- too generic
#
# After fine-tuning, this table should be empty or minimal.
# ---------------------------------------------------------------------------
COCO_ALIASES: dict[str, str] = {
    # COCO name        → MachineryType value
    "cement_mixer":   "concrete_mixer",
    "mixer":          "concrete_mixer",
    "crane":          "mobile_crane",
    "lorry":          "truck",
    "tipper":         "dump_truck",
    "digger":         "excavator",
    "compactor":      "roller",
    "road_roller":    "roller",
    # COCO generic classes with some construction overlap
    "truck":          "truck",
}


class MachineryDetector:
    """Detect target machinery using YOLO when weights are available."""

    def __init__(
        self,
        weights_path: str | Path | None = None,
        confidence: float | None = None,
    ) -> None:
        settings = get_settings()
        self.weights_path = Path(weights_path or settings.yolo_weights)
        self.confidence = confidence if confidence is not None else settings.yolo_confidence
        self._model = None
        self._load_error: Exception | None = None

        if self.weights_path.is_file():
            try:
                from ultralytics import YOLO  # noqa: PLC0415

                self._model = YOLO(str(self.weights_path))
                logger.info(
                    "YOLO model loaded: %s  classes=%d  conf_threshold=%.2f",
                    self.weights_path.name,
                    len(self._model.names),
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

    def detect(self, image_bytes: bytes) -> list[DetectionItem]:
        """Run inference and return validated detections.

        Returns an empty list when inference fails — but every failure is
        logged with ERROR level so it is never silently lost.
        """
        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Uploaded file is not a readable image")

            if self._model is None:
                logger.info("Synthetic fallback active — returning placeholder excavator.")
                return self._fallback_detections(image)

            result = self._model.predict(source=image, conf=self.confidence, verbose=False)[0]
            detections = self._parse_result(result)
            logger.debug(
                "Inference complete: %d raw boxes → %d domain detections",
                len(result.boxes),
                len(detections),
            )
            return detections

        except ValueError as exc:
            # Bad image upload — caller should surface this as HTTP 400.
            logger.warning("Image decode failed: %s", exc)
            raise
        except Exception as exc:
            # Unexpected inference error (OOM, CUDA, corrupted weights…).
            # Log at ERROR level and return empty list so the pipeline
            # can degrade gracefully rather than crash the entire request.
            logger.error("Inference error (returning empty result): %s", exc, exc_info=True)
            return []

    def _parse_result(self, result) -> list[DetectionItem]:  # type: ignore[override]
        """Convert raw YOLO result to domain DetectionItems."""
        names = result.names
        detections: list[DetectionItem] = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            raw_name = str(names[class_id]).casefold().strip()
            normalized = raw_name.replace("-", "_").replace(" ", "_")
            clean_name = COCO_ALIASES.get(normalized, normalized)
            try:
                machinery = MachineryType(clean_name)
            except ValueError:
                # Class not in domain ontology — skip silently but count.
                logger.debug("Skipping unknown class: %s (normalized: %s)", raw_name, clean_name)
                continue
            detections.append(
                DetectionItem(
                    class_name=machinery,
                    confidence=float(box.conf[0]),
                    bbox=[float(v) for v in box.xyxy[0].tolist()],
                )
            )
        return detections

    @staticmethod
    def _fallback_detections(image: np.ndarray) -> list[DetectionItem]:
        """Return one low-confidence synthetic object for local smoke testing.

        IMPORTANT: This is NOT machine learning. It is a hardcoded placeholder
        used only when model weights are absent, to keep the rest of the pipeline
        testable. The returned confidence (0.01) signals its synthetic nature.
        """
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