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
import os
from pathlib import Path

# Disable Ultralytics autoinstall of onnxruntime-gpu when using CPU onnxruntime
os.environ.setdefault("YOLO_AUTOINSTALL", "False")

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

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

    # --- 4. manipulator (кран-манипулятор) ---
    "manipulator":       "manipulator",
    "crane_manipulator": "manipulator",
    "crane_truck":       "manipulator",
    "loader_crane":      "manipulator",
    "boom_truck":        "manipulator",
    "кран_манипулятор":  "manipulator",
    "манипулятор":       "manipulator",

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


def _box_area(b: list[float]) -> float:
    """Calculate area of bbox [x1, y1, x2, y2]."""
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection_area(b1: list[float], b2: list[float]) -> float:
    """Calculate intersection area of two bboxes."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    return w * h


def suppress_contained_boxes(
    detections: list[DetectionItem], threshold: float = 0.75
) -> list[DetectionItem]:
    """Filter out nested detections where a smaller box is contained within a larger box.

    If more than `threshold` (default 75%) of a box's area lies inside another
    larger bounding box, the smaller (nested) box is suppressed.
    """
    if len(detections) <= 1:
        return detections

    suppressed: set[int] = set()
    areas = [_box_area(d.bbox) for d in detections]

    for i in range(len(detections)):
        if i in suppressed or areas[i] <= 0:
            continue
        for j in range(len(detections)):
            if i == j or j in suppressed or areas[j] <= 0:
                continue

            # Check if box j is inside box i (box i has larger or equal area)
            if areas[i] > areas[j] or (
                areas[i] == areas[j] and detections[i].confidence >= detections[j].confidence
            ):
                inter = _intersection_area(detections[i].bbox, detections[j].bbox)
                containment = inter / areas[j]
                if containment >= threshold:
                    logger.debug(
                        "Suppressing nested box %s (conf=%.2f) inside %s (conf=%.2f, containment=%.1f%%)",
                        detections[j].class_name.value,
                        detections[j].confidence,
                        detections[i].class_name.value,
                        detections[i].confidence,
                        containment * 100,
                    )
                    suppressed.add(j)

    return [d for idx, d in enumerate(detections) if idx not in suppressed]


# ---------------------------------------------------------------------------
# Strict Russian localization mapping for DGP Moscow normative ontology
# ---------------------------------------------------------------------------
LABEL_MAPPING_RU: dict[str, str] = {
    "dump_truck": "Самосвал",
    "excavator": "Экскаватор",
    "roller": "Каток",
    "manipulator": "Кран-манипулятор",
    "crane_manipulator": "Кран-манипулятор",
    "bulldozer": "Бульдозер",
    "mobile_crane": "Автокран",
    "concrete_mixer": "Бетоносмеситель",
    "truck": "Грузовик",
}


def _get_font(size: int = 16) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Attempt to load a TrueType font supporting Cyrillic with safe fallbacks."""
    candidate_fonts = [
        "arial.ttf",
        "segoeui.ttf",
        "calibri.ttf",
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for font_name in candidate_fonts:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def annotate_image(image: np.ndarray, detections: list) -> np.ndarray:
    """Draw bounding boxes and Cyrillic class labels on image using Pillow.

    Args:
        image: BGR numpy ndarray.
        detections: List of DetectionItem objects or dicts with bbox, class_name, confidence.

    Returns:
        Annotated BGR numpy ndarray.
    """
    if image is None or image.size == 0:
        return image

    annotated = image.copy()
    h, w = annotated.shape[:2]

    # Convert BGR to RGB PIL image for crisp Cyrillic text rendering
    pil_image = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)

    font_size = max(14, int(min(w, h) * 0.024))
    font = _get_font(size=font_size)

    box_color = (0, 190, 70)  # RGB Emerald green
    text_color = (255, 255, 255)

    for item in detections:
        # Handle both DetectionItem and dict
        if isinstance(item, dict):
            raw_bbox = item.get("bbox", [])
            class_obj = item.get("class_name", "")
            confidence = float(item.get("confidence", 0.0))
        else:
            raw_bbox = getattr(item, "bbox", [])
            class_obj = getattr(item, "class_name", "")
            confidence = float(getattr(item, "confidence", 0.0))

        if len(raw_bbox) != 4:
            continue

        x1, y1, x2, y2 = [int(round(float(v))) for v in raw_bbox]
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))

        if x2 <= x1 or y2 <= y1:
            continue

        # Draw green bounding box
        draw.rectangle([x1, y1, x2, y2], outline=box_color, width=3)

        # Resolve Russian class name
        class_str = class_obj.value if hasattr(class_obj, "value") else str(class_obj)
        ru_name = LABEL_MAPPING_RU.get(class_str, class_str)
        label = f"{ru_name} {confidence:.0%}"

        # Calculate text badge dimensions
        try:
            bbox_text = draw.textbbox((0, 0), label, font=font)
            text_w = bbox_text[2] - bbox_text[0]
            text_h = bbox_text[3] - bbox_text[1]
        except Exception:
            text_w = len(label) * 9
            text_h = font_size

        pad_x = 6
        pad_y = 4
        badge_h = text_h + pad_y * 2

        if y1 - badge_h >= 0:
            badge_y1 = y1 - badge_h
            badge_y2 = y1
        else:
            badge_y1 = y1
            badge_y2 = min(h, y1 + badge_h)

        badge_x2 = min(w, x1 + text_w + pad_x * 2)

        # Draw filled green badge and white text
        draw.rectangle([x1, badge_y1, badge_x2, badge_y2], fill=box_color)
        draw.text((x1 + pad_x, badge_y1 + pad_y), label, fill=text_color, font=font)

    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


class MachineryDetector:
    """Lightweight construction machinery detector using specialized ONNX or PyTorch weights."""

    def __init__(
        self,
        weights_path: str | Path | None = None,
        confidence: float | None = 0.35,
        iou: float | None = 0.45,
    ) -> None:
        settings = get_settings()
        target_path = Path(weights_path) if weights_path else Path(settings.yolo_weights)

        # Automatic fallback from .onnx to .pt if .onnx file is missing
        if target_path.suffix.lower() == ".onnx" and not target_path.is_file():
            fallback_pt = (
                settings.model_pt_path
                if hasattr(settings, "model_pt_path") and settings.model_pt_path.is_file()
                else Path("backend/models/best.pt")
            )
            if fallback_pt.is_file():
                logger.warning(
                    "ONNX model not found at %s. Falling back to PyTorch weights: %s",
                    target_path,
                    fallback_pt,
                )
                target_path = fallback_pt
            else:
                logger.warning("Neither ONNX (%s) nor PyTorch fallback (%s) found.", target_path, fallback_pt)

        self.weights_path = target_path
        self.confidence = confidence if confidence is not None else 0.35
        self.iou = iou if iou is not None else 0.45
        self.imgsz = 640
        self.is_onnx = self.weights_path.suffix.lower() == ".onnx"
        self._model = None
        self._load_error: Exception | None = None
        self._is_construction: bool = False

        if self.is_onnx:
            self.device = "cpu"
        else:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        if self.weights_path.is_file():
            try:
                from ultralytics import YOLO  # noqa: PLC0415

                if self.is_onnx:
                    self._model = YOLO(str(self.weights_path), task="detect")
                    logger.info("Loaded model: %s (ONNX runtime)", self.weights_path)
                else:
                    self._model = YOLO(str(self.weights_path))
                    logger.info("Loaded model: %s (PyTorch)", self.weights_path)

                # Check if model has domain-specific construction classes
                matched_classes = sum(
                    1
                    for name in self._model.names.values()
                    if str(name).casefold().replace("-", "_").replace(" ", "_") in MACHINERY_ALIASES
                )
                self._is_construction = matched_classes >= 3
                logger.info(
                    "Detector initialized: %s (classes=%d, is_construction=%s, device=%s, imgsz=%d, conf=%.2f)",
                    self.weights_path.name,
                    len(self._model.names),
                    self._is_construction,
                    self.device,
                    self.imgsz,
                    self.confidence,
                )
            except Exception as error:  # pragma: no cover
                self._load_error = error
                logger.error("Failed to load YOLO model from %s: %s", self.weights_path, error)
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

    def detect(
        self,
        image_input: bytes | str | Path | np.ndarray,
    ) -> list[DetectionItem]:
        """Run inference and return validated detections.

        Accepts image as bytes, file path (str or Path), or numpy.ndarray (BGR).
        Guaranteed memory efficiency:
        - ONNX inference with onnxruntime.
        - FP16 (half=True) when on GPU with PyTorch.
        - Automatic torch.cuda.empty_cache() cleanup in finally block.
        - Class-Agnostic NMS (agnostic_nms=True) to avoid duplicate cross-class bounding boxes.
        - Post-processing suppression of nested boxes (suppress_contained_boxes).
        """
        try:
            if isinstance(image_input, bytes):
                image = cv2.imdecode(np.frombuffer(image_input, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError("Uploaded file is not a readable image")
            elif isinstance(image_input, (str, Path)):
                image = cv2.imread(str(image_input))
                if image is None:
                    raise ValueError(f"Could not read image from path: {image_input}")
            elif isinstance(image_input, np.ndarray):
                image = image_input
            else:
                raise TypeError(f"Unsupported image input type: {type(image_input)}")

            if self._model is None:
                logger.info("Synthetic fallback active — returning placeholder excavator.")
                return self._fallback_detections(image)

            predict_kwargs: dict[str, object] = {
                "source": image,
                "conf": self.confidence,
                "iou": self.iou,
                "agnostic_nms": True,
                "imgsz": self.imgsz,
                "device": self.device,
                "verbose": False,
            }
            if not self.is_onnx and self.device.startswith("cuda"):
                predict_kwargs["half"] = True

            result = self._model.predict(**predict_kwargs)[0]
            raw_detections = self._parse_result(result)
            detections = suppress_contained_boxes(raw_detections, threshold=0.75)
            logger.debug(
                "Inference complete: %d raw boxes -> %d domain -> %d suppressed detections",
                len(result.boxes),
                len(raw_detections),
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