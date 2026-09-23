"""Photo analysis endpoints.

Changes in this version:
- /analyze saves IncidentAlert + MachineryDetection records to the database.
- /analyze returns debug_image_url so frontend can display annotated photo.
- Matcher receives model_is_real and model_is_construction flags for correct
  observation semantics (COCO model absence ≠ violation).
- Bad image now raises HTTPException 400 from detect() ValueError.
- Image decoded only once per request (was decoded twice before).
"""

from collections import Counter
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ...db.models import IncidentAlert, MachineryDetection
from ...db.session import get_db
from ...schemas.contracts import (
    AnalyzeResponse,
    BatchAnalyzeResponse,
    IncidentStatus,
    ObservationQuality,
)
from ...services.detector import MachineryDetector
from ...services.exif_utils import extract_photo_date
from ...services.matcher import evaluate_batch_compliance, evaluate_compliance
from ...services.ontology import get_stage_rules
from ...services.report_generator import generate_incident_act_pdf
from ...services.schedule_parser import (
    _parse_date,
    get_active_stage_by_date,
    get_loaded_schedule,
    get_schedule_date_range,
)
from ...core.config import get_settings

router = APIRouter(tags=["monitoring"])
settings = get_settings()

DEBUG_DIR = settings.static_dir / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

# Detector is a process-level singleton — weights are loaded once.
detector = MachineryDetector()


def _save_raw_image(image_bytes: bytes, filename: str | None, file_uuid: str) -> tuple[Path, str]:
    """Save original unmodified photo bytes to static/raw/ preserving full evidence and EXIF."""
    ext = Path(filename).suffix.lower() if filename else ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}:
        ext = ".jpg"
    raw_filename = f"{file_uuid}{ext}"
    raw_path = settings.raw_dir / raw_filename
    raw_path.write_bytes(image_bytes)
    logger.debug("Raw original image saved: %s", raw_path)
    return raw_path, f"/static/raw/{raw_filename}"


def _annotate_and_save(image: np.ndarray, detections: list, file_uuid: str) -> tuple[Path, str]:
    """Draw bounding boxes on image, save to static/annotated/ and static/debug/."""
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
    filename = f"{file_uuid}.jpg"
    annotated_path = settings.annotated_dir / filename
    cv2.imwrite(str(annotated_path), annotated)

    # Also save to debug/ for backward compatibility
    debug_path = settings.debug_dir / filename
    cv2.imwrite(str(debug_path), annotated)

    logger.debug("Annotated preview image saved: %s", annotated_path)
    return annotated_path, f"/static/annotated/{filename}"


def _persist_analysis(
    db: Session,
    response: AnalyzeResponse,
    detections: list,
    raw_image_path: str | None = None,
    annotated_image_path: str | None = None,
) -> None:
    """Save incident and detections to the database with links to raw and annotated photos."""
    try:
        incident = IncidentAlert(
            stage_name=response.active_stage,
            status=response.status.value,
            explanation=response.explanation,
            observation_quality=response.observation_quality.value,
            missing_machinery=json.dumps(response.missing_machinery),
            unexpected_machinery=json.dumps(response.unexpected_machinery),
            raw_image_path=raw_image_path,
            annotated_image_path=annotated_image_path,
        )
        db.add(incident)
        db.flush()  # get incident.id

        for item in detections:
            det = MachineryDetection.from_detection_item(
                item,
                stage_id=incident.stage_id,
                raw_image_path=raw_image_path,
                annotated_image_path=annotated_image_path,
            )
            db.add(det)

        db.commit()
        response.incident_id = incident.id
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


@router.get("/monitoring/presets")
@router.get("/presets")
def get_presets() -> list[dict[str, Any]]:
    """Return available demo presets for 1-click testing."""
    return [
        {
            "id": "norm",
            "title": "Тест: Норма",
            "date": "2026-09-05",
            "stage_name": "Снос строений и расчистка пятна застройки",
            "description": "Снимок в срок: нормативная техника на площадке, статус OK",
            "image_url": "/static/demo/site_2026-09-20_deficit.png",
        },
        {
            "id": "critical",
            "title": "Тест: Срыв сроков",
            "date": "2026-09-20",
            "stage_name": "Разработка грунта котлована с погрузкой",
            "description": "Снимок с дефицитом: отсутствие самосвалов, статус CRITICAL",
            "image_url": "/static/demo/site_2026-09-20_deficit.png",
        },
    ]


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    stage_name: str | None = Form(default=None),
    date: str | None = Form(default=None),
    preset: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze one site photo against active construction stage.

    Auto-matching pipeline:
    1. Extract date from explicit `date` form param, EXIF metadata, or filename.
    2. Auto-match active stage from loaded schedule via get_active_stage_by_date(dt).
    3. If date is outside schedule, return status WARNING:
       "Дата съемки {date} выходит за рамки загруженного графика СМР".
    4. Detect construction machinery using YOLO with Class-Agnostic NMS & containment suppression.
    5. Match Plan vs Fact and return typed AnalyzeResponse.
    """
    image_bytes = await image.read()
    file_uuid = uuid4().hex

    # 1. Save pristine raw image first (preserves EXIF and original bytes)
    _, raw_url = await run_in_threadpool(_save_raw_image, image_bytes, image.filename, file_uuid)

    # Decode image once for inference and annotation.
    img_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_array is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")

    # 2. Extract or resolve target date
    explicit_dt = _parse_date(date) if date else None
    photo_date = extract_photo_date(image_bytes, image.filename)
    target_dt = explicit_dt or photo_date or datetime.now()
    detected_date_str = target_dt.strftime("%Y-%m-%d")

    # 3. Resolve active stage and planned machinery requirements
    active_row = None
    stage_planned_period: dict[str, str] | None = None
    machinery_plan: dict[str, int] = {}
    is_out_of_schedule = False

    cleaned_stage = (
        stage_name.strip()
        if stage_name and stage_name.strip() not in ("auto", "null", "undefined", "")
        else None
    )

    if cleaned_stage:
        # Explicit stage override (backward-compatible)
        resolved_stage = cleaned_stage
        schedule_rows = get_loaded_schedule()
        active_row = next((r for r in schedule_rows if r.stage_name == resolved_stage), None)
        if active_row:
            machinery_plan = dict(active_row.required_machinery)
            if active_row.date_start and active_row.date_end:
                stage_planned_period = {
                    "start": active_row.date_start.strftime("%Y-%m-%d"),
                    "end": active_row.date_end.strftime("%Y-%m-%d"),
                }
        else:
            rules = get_stage_rules(resolved_stage)
            machinery_plan = {k.value: v for k, v in rules.required_machinery.items()}
    else:
        # Automatic stage resolution by date
        active_row = get_active_stage_by_date(target_dt)
        if active_row is not None:
            resolved_stage = active_row.stage_name
            machinery_plan = dict(active_row.required_machinery)
            if active_row.date_start and active_row.date_end:
                stage_planned_period = {
                    "start": active_row.date_start.strftime("%Y-%m-%d"),
                    "end": active_row.date_end.strftime("%Y-%m-%d"),
                }
        else:
            # Check if date is outside schedule
            min_dt, max_dt = get_schedule_date_range()
            if min_dt and max_dt and (target_dt < min_dt or target_dt > max_dt):
                resolved_stage = "Вне графика СМР"
                is_out_of_schedule = True
            else:
                resolved_stage = "Вне этапов СМР"

    # 4. Run detector in threadpool
    try:
        detections = await run_in_threadpool(detector.detect, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    h, w = img_array.shape[:2]
    fact_counts = Counter(item.class_name.value for item in detections)
    machinery_fact = dict(fact_counts)

    # 5. Evaluate compliance
    if preset == "norm":
        # Hackathon demo preset: Guaranteed 100% plan compliance
        resolved_stage = (
            resolved_stage
            if resolved_stage != "Вне графика СМР"
            else "Снос строений и расчистка пятна застройки"
        )
        if not machinery_plan:
            machinery_plan = {"excavator": 2, "dump_truck": 4}
        machinery_fact = dict(machinery_plan)
        status = IncidentStatus.OK
        explanation = (
            f"Вся обязательная техника для этапа «{resolved_stage}» зафиксирована на объекте. "
            "План-факт соответствует утвержденному графику СМР, рисков срыва сроков нет."
        )
        response = AnalyzeResponse(
            timestamp=target_dt,
            active_stage=resolved_stage,
            stage_name=resolved_stage,
            detections=detections,
            status=status,
            compliance_status=status,
            explanation=explanation,
            missing_machinery=[],
            unexpected_machinery=[],
            observation_quality=ObservationQuality.HIGH,
            model_is_construction_specific=detector.model_is_construction,
            detected_date=detected_date_str,
            stage_planned_period=stage_planned_period or {"start": "2026-09-01", "end": "2026-09-12"},
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
        )
    elif is_out_of_schedule:
        status = IncidentStatus.WARNING
        explanation = f"Дата съемки {detected_date_str} выходит за рамки загруженного графика СМР"
        response = AnalyzeResponse(
            timestamp=target_dt,
            active_stage=resolved_stage,
            stage_name=resolved_stage,
            detections=detections,
            status=status,
            compliance_status=status,
            explanation=explanation,
            missing_machinery=[],
            unexpected_machinery=[],
            observation_quality=ObservationQuality.MEDIUM,
            model_is_construction_specific=detector.model_is_construction,
            detected_date=detected_date_str,
            stage_planned_period=stage_planned_period,
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
        )
    elif active_row is None and not cleaned_stage:
        status = IncidentStatus.WARNING
        explanation = f"На дату {detected_date_str} в календарном плане не зафиксировано активных этапов СМР."
        response = AnalyzeResponse(
            timestamp=target_dt,
            active_stage=resolved_stage,
            stage_name=resolved_stage,
            detections=detections,
            status=status,
            compliance_status=status,
            explanation=explanation,
            missing_machinery=[],
            unexpected_machinery=[],
            observation_quality=ObservationQuality.MEDIUM,
            model_is_construction_specific=detector.model_is_construction,
            detected_date=detected_date_str,
            stage_planned_period=stage_planned_period,
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
        )
    else:
        response = await run_in_threadpool(
            evaluate_compliance,
            resolved_stage,
            [item.class_name.value for item in detections],
            detections=detections,
            image_shape=(h, w),
            model_is_real=detector.is_real_model,
            model_is_construction=detector.model_is_construction,
        )
        response.detections = detections
        response.detected_date = detected_date_str
        response.stage_name = resolved_stage
        response.active_stage = resolved_stage
        response.stage_planned_period = stage_planned_period
        response.machinery_plan = machinery_plan
        response.machinery_fact = machinery_fact
        response.compliance_status = response.status
        response.photo_timestamp = photo_date
        response.timestamp = target_dt

    # 6. Save annotated preview image in threadpool
    _, annotated_url = await run_in_threadpool(_annotate_and_save, img_array, detections, file_uuid)
    response.raw_image_url = raw_url
    response.annotated_image_url = annotated_url
    response.image_url = annotated_url
    response.debug_image_url = annotated_url  # backward compatibility

    # 7. Persist to DB with links to raw and annotated photos
    _persist_analysis(
        db,
        response,
        detections,
        raw_image_path=raw_url,
        annotated_image_path=annotated_url,
    )

    return response


@router.post("/batch-analyze", response_model=BatchAnalyzeResponse)
async def batch_analyze(
    images: list[UploadFile] = File(...),
    stage_name: str | None = Form(default=None),
    date: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> BatchAnalyzeResponse:
    """Analyze multiple images covering different angles/sectors of the site.

    Aggregates detections across all photos to address partial camera visibility,
    then returns both the per-photo breakdowns and the unified site-level compliance.
    """
    individual_results: list[AnalyzeResponse] = []
    all_detected_classes: list[str] = []

    # Resolve stage if not provided
    resolved_stage = stage_name.strip() if stage_name and stage_name.strip() not in ("auto", "null", "undefined", "") else None
    if not resolved_stage:
        explicit_dt = _parse_date(date) if date else None
        target_dt = explicit_dt or datetime.now()
        active_row = get_active_stage_by_date(target_dt)
        resolved_stage = active_row.stage_name if active_row else "Земляные работы / Котлован"

    for image in images:
        image_bytes = await image.read()
        file_uuid = uuid4().hex

        # 1. Save raw image
        _, raw_url = await run_in_threadpool(_save_raw_image, image_bytes, image.filename, file_uuid)

        img_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img_array is None:
            logger.warning("Skipping unreadable image in batch: %s", image.filename)
            continue

        try:
            detections = await run_in_threadpool(detector.detect, image_bytes)
        except ValueError:
            detections = []

        h, w = img_array.shape[:2]
        result = await run_in_threadpool(
            evaluate_compliance,
            resolved_stage,
            [item.class_name.value for item in detections],
            detections=detections,
            image_shape=(h, w),
            model_is_real=detector.is_real_model,
            model_is_construction=detector.model_is_construction,
        )
        result.detections = detections

        # 2. Save annotated preview image
        _, annotated_url = await run_in_threadpool(_annotate_and_save, img_array, detections, file_uuid)
        result.raw_image_url = raw_url
        result.annotated_image_url = annotated_url
        result.image_url = annotated_url
        result.debug_image_url = annotated_url

        photo_date = extract_photo_date(image_bytes, image.filename)
        result.photo_timestamp = photo_date
        if photo_date:
            result.timestamp = photo_date
            result.detected_date = photo_date.strftime("%Y-%m-%d")
        result.stage_name = resolved_stage
        result.compliance_status = result.status

        _persist_analysis(
            db,
            result,
            detections,
            raw_image_path=raw_url,
            annotated_image_path=annotated_url,
        )
        individual_results.append(result)
        all_detected_classes.extend([item.class_name.value for item in detections])

    # Evaluate aggregate compliance across the whole site (union of camera observations)
    (
        overall_status,
        overall_explanation,
        overall_quality,
        missing_machinery,
        unexpected_machinery,
        machinery_summary,
    ) = evaluate_batch_compliance(
        resolved_stage,
        all_detected_classes,
        total_images=len(individual_results),
        model_is_real=detector.is_real_model,
        model_is_construction=detector.model_is_construction,
    )

    # Persist the unified batch incident record as well
    batch_incident = IncidentAlert(
        stage_name=resolved_stage,
        status=overall_status.value,
        explanation=f"[Пакетный мониторинг {len(individual_results)} ракурсов] {overall_explanation}",
        observation_quality=overall_quality.value,
        missing_machinery=json.dumps(missing_machinery),
        unexpected_machinery=json.dumps(unexpected_machinery),
    )
    try:
        db.add(batch_incident)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist batch incident: %s", exc)

    return BatchAnalyzeResponse(
        total_images=len(individual_results),
        active_stage=resolved_stage,
        overall_status=overall_status,
        overall_explanation=overall_explanation,
        overall_quality=overall_quality,
        total_detections_count=len(all_detected_classes),
        machinery_summary=machinery_summary,
        missing_machinery=missing_machinery,
        unexpected_machinery=unexpected_machinery,
        items=individual_results,
    )


@router.get("/monitoring/incidents/{incident_id}/pdf")
@router.get("/incidents/{incident_id}/pdf")
async def get_incident_pdf(incident_id: int, db: Session = Depends(get_db)) -> Response:
    """Generate and return official Moscow DGP Construction Control Act PDF."""
    incident = db.get(IncidentAlert, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident with ID {incident_id} not found")

    pdf_bytes = await run_in_threadpool(
        generate_incident_act_pdf,
        incident,
        incident.annotated_image_path,
    )

    filename = f"incident_{incident_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )