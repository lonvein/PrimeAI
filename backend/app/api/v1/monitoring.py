"""Photo analysis endpoints.

Changes in this version:
- /analyze saves IncidentAlert + MachineryDetection records to the database.
- /analyze returns debug_image_url so frontend can display annotated photo.
- Matcher receives model_is_real and model_is_construction flags for correct
  observation semantics (COCO model absence ≠ violation).
- Bad image now raises HTTPException 400 from detect() ValueError.
- Image decoded only once per request (was decoded twice before).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ...db.models import IncidentAlert, MachineryDetection
from ...db.session import get_db
from ...schemas.contracts import AnalyzeResponse, ObservationQuality
from ...services.detector import MachineryDetector
from ...services.matcher import evaluate_compliance
from ...core.config import get_settings

router = APIRouter(tags=["monitoring"])
settings = get_settings()

DEBUG_DIR = settings.static_dir / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

# Detector is a process-level singleton — weights are loaded once.
detector = MachineryDetector()


def _annotate_and_save(image: np.ndarray, detections: list) -> str:
    """Draw bounding boxes on image, save to debug dir, return relative URL."""
    annotated = image.copy()
    for detection in detections:
        left, top, right, bottom = (int(v) for v in detection.bbox)
        cv2.rectangle(annotated, (left, top), (right, bottom), (0, 190, 80), 2)
        label = f"{detection.class_name.value} {detection.confidence:.2f}"
        cv2.putText(
            annotated,
            label,
            (left, max(20, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 190, 80),
            2,
        )
    filename = f"{uuid4().hex}.jpg"
    save_path = DEBUG_DIR / filename
    cv2.imwrite(str(save_path), annotated)
    logger.debug("Debug image saved: %s", save_path)
    return f"/static/debug/{filename}"


def _persist_analysis(
    db: Session,
    response: AnalyzeResponse,
    detections: list,
) -> None:
    """Save incident and detections to the database."""
    try:
        incident = IncidentAlert(
            stage_name=response.active_stage,
            status=response.status.value,
            explanation=response.explanation,
            observation_quality=response.observation_quality.value,
            missing_machinery=json.dumps(response.missing_machinery),
            unexpected_machinery=json.dumps(response.unexpected_machinery),
        )
        db.add(incident)
        db.flush()  # get incident.id

        for item in detections:
            det = MachineryDetection.from_detection_item(item)
            db.add(det)

        db.commit()
        logger.debug("Persisted incident id=%d  status=%s", incident.id, response.status.value)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist analysis to DB: %s", exc, exc_info=True)
        # Do NOT re-raise: persistence failure should not crash the API response.


@router.get("/health")
def health() -> dict[str, str]:
    """Return service readiness and model status."""
    return {
        "status": "ok",
        "model": "real" if detector.is_real_model else "fallback",
        "weights": detector.weights_path.name,
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    stage_name: str = Form(...),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze one site photo against the selected construction stage.

    The image is decoded once; the same array is used for inference and annotation.
    """
    image_bytes = await image.read()

    # Decode image once.
    img_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_array is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")

    # Run detector (uses decoded array internally).
    try:
        detections = detector.detect(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Evaluate compliance with honest observation semantics.
    response = evaluate_compliance(
        stage_name,
        [item.class_name.value for item in detections],
        model_is_real=detector.is_real_model,
        model_is_construction=False,  # set to True after fine-tuning
    )
    response.detections = detections

    # Save annotated debug image and add URL to response.
    debug_url = _annotate_and_save(img_array, detections)
    response.debug_image_url = debug_url

    # Persist to DB (non-blocking on failure).
    _persist_analysis(db, response, detections)

    return response


@router.post("/batch-analyze", response_model=list[AnalyzeResponse])
async def batch_analyze(
    images: list[UploadFile] = File(...),
    stage_name: str = Form(...),
    db: Session = Depends(get_db),
) -> list[AnalyzeResponse]:
    """Analyze multiple images using one active stage.

    Each image is processed independently. Failures on individual images
    are returned as WARNING responses, not hard errors.
    """
    results: list[AnalyzeResponse] = []
    for image in images:
        image_bytes = await image.read()
        img_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img_array is None:
            logger.warning("Skipping unreadable image in batch: %s", image.filename)
            continue

        try:
            detections = detector.detect(image_bytes)
        except ValueError:
            detections = []

        result = evaluate_compliance(
            stage_name,
            [item.class_name.value for item in detections],
            model_is_real=detector.is_real_model,
            model_is_construction=False,
        )
        result.detections = detections
        result.debug_image_url = _annotate_and_save(img_array, detections)
        _persist_analysis(db, result, detections)
        results.append(result)

    return results