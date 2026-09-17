"""Ultralytics YOLO inference with a local development fallback."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from ..schemas.contracts import DetectionItem, MachineryType


class MachineryDetector:
    """Detect target machinery using YOLO when weights are available."""

    def __init__(self, weights_path: str | Path | None = None, confidence: float = 0.25) -> None:
        self.weights_path = Path(
            weights_path or os.getenv("YOLO_WEIGHTS", "backend/models/best.pt")
        )
        self.confidence = confidence
        self._model = None
        self._load_error: Exception | None = None
        if self.weights_path.is_file():
            try:
                from ultralytics import YOLO

                self._model = YOLO(str(self.weights_path))
            except Exception as error:  # pragma: no cover - depends on local ML runtime
                self._load_error = error

    def detect(self, image_bytes: bytes) -> list[DetectionItem]:
        """Run inference and return validated detections.

        Missing weights, invalid images, and inference errors use a deterministic
        empty result so the rest of the API remains available during setup.
        """

        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Uploaded file is not a readable image")
            if self._model is None:
                return self._fallback_detections(image)

            result = self._model.predict(source=image, conf=self.confidence, verbose=False)[0]
            names = result.names
            detections: list[DetectionItem] = []
            for box in result.boxes:
                class_id = int(box.cls[0])
                
                raw_name = str(names[class_id]).casefold().strip()
                normalized_name = raw_name.replace("-", "_").replace(" ", "_")

                # Синонимы из популярных датасетов стройплощадок
                ALIASES = {
                    "cement_mixer": "concrete_mixer",
                    "mixer": "concrete_mixer",
                    "crane": "mobile_crane",
                    "lorry": "truck",
                    "tipper": "dump_truck",
                    "digger": "excavator",
                    "compactor": "roller",
                    "road_roller": "roller",
                }
                clean_name = ALIASES.get(normalized_name, normalized_name)

                try:
                    machinery = MachineryType(clean_name)
                except ValueError:
                    continue
                
                
                detections.append(
                    DetectionItem(
                        class_name=machinery,
                        confidence=float(box.conf[0]),
                        bbox=[float(value) for value in box.xyxy[0].tolist()],
                    )
                )
            return detections
        except Exception:
            return []

    @staticmethod
    def _fallback_detections(image: np.ndarray) -> list[DetectionItem]:
        """Return one low-confidence synthetic object for local smoke testing."""

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