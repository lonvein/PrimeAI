"""Photo analysis endpoints."""

from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...schemas.contracts import AnalyzeResponse
from ...services.detector import MachineryDetector
from ...services.matcher import evaluate_compliance

router = APIRouter(tags=["monitoring"])
DEBUG_DIR = Path(__file__).resolve().parents[3] / "static" / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
detector = MachineryDetector()


def _save_debug_image(image_bytes: bytes, detections: list) -> None:
    """Save a detector result with bounding boxes for local inspection."""

    decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")
    for detection in detections:
        left, top, right, bottom = (int(value) for value in detection.bbox)
        cv2.rectangle(decoded, (left, top), (right, bottom), (0, 190, 80), 2)
        cv2.putText(
            decoded,
            f"{detection.class_name.value} {detection.confidence:.2f}",
            (left, max(20, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 190, 80),
            2,
        )
    cv2.imwrite(str(DEBUG_DIR / f"{uuid4().hex}.jpg"), decoded)


@router.get("/health")
def health() -> dict[str, str]:
    """Return service readiness."""

    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(image: UploadFile = File(...), stage_name: str = Form(...)) -> AnalyzeResponse:
    """Analyze one site photo against the selected construction stage."""

    image_bytes = await image.read()
    detections = detector.detect(image_bytes)
    response = evaluate_compliance(stage_name, [item.class_name.value for item in detections])
    response.detections = detections
    _save_debug_image(image_bytes, detections)
    return response


@router.post("/batch-analyze", response_model=list[AnalyzeResponse])
async def batch_analyze(
    images: list[UploadFile] = File(...), stage_name: str = Form(...)
) -> list[AnalyzeResponse]:
    """Analyze multiple images using one active stage."""

    results: list[AnalyzeResponse] = []
    for image in images:
        image_bytes = await image.read()
        detections = detector.detect(image_bytes)
        result = evaluate_compliance(stage_name, [item.class_name.value for item in detections])
        result.detections = detections
        _save_debug_image(image_bytes, detections)
        results.append(result)
    return results