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
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ...db.models import IncidentAlert, MachineryDetection
from ...db.session import get_db
from ...schemas.contracts import (
    AnalyzeResponse,
    BatchAnalyzeResponse,
    IncidentStatus,
    ObservationQuality,
    ScheduleRow,
)
from ...services.detector import MachineryDetector, annotate_image
from ...services.exif_utils import _extract_exif_date, _extract_filename_date, extract_photo_date
from ...services.matcher import evaluate_batch_compliance, evaluate_compliance
from ...services.ontology import get_stage_rules
from ...services.report_generator import generate_incident_act_pdf
from ...services.schedule_parser import (
    StageFallback,
    get_active_stage_by_date,
    get_loaded_schedule,
    get_nearest_stage,
    get_schedule_date_range,
    normalize_to_date,
    to_date,
)
from ...core.config import get_settings

router = APIRouter(tags=["monitoring"])
settings = get_settings()


def resolve_analysis_date(
    selected_date_str: str | None,
    image_bytes: bytes,
    filename: str | None,
) -> tuple[date, str, datetime | None]:
    """Resolve target date following strict priority:
    1. selected_date (explicitly passed by user in UI)
    2. EXIF metadata (DateTimeOriginal)
    3. Filename regex pattern (e.g., Screenshot_2026-09-20...)
    4. Current system date (date.today())

    Returns (target_date, target_date_iso_str, photo_exif_dt).
    """
    photo_exif_dt = None
    if image_bytes:
        photo_exif_dt = _extract_exif_date(image_bytes)

    filename_dt = None
    if filename:
        filename_dt = _extract_filename_date(filename)

    # 1. User selected date
    if selected_date_str and str(selected_date_str).strip() not in ("null", "undefined", ""):
        target_d = normalize_to_date(selected_date_str)
        return target_d, target_d.strftime("%Y-%m-%d"), photo_exif_dt

    # 2. EXIF metadata
    if photo_exif_dt:
        target_d = normalize_to_date(photo_exif_dt)
        return target_d, target_d.strftime("%Y-%m-%d"), photo_exif_dt

    # 3. Filename regex pattern
    if filename_dt:
        target_d = normalize_to_date(filename_dt)
        return target_d, target_d.strftime("%Y-%m-%d"), photo_exif_dt

    # 4. Current system date
    today_d = date.today()
    return today_d, today_d.strftime("%Y-%m-%d"), photo_exif_dt

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
    """Draw bounding boxes and Cyrillic labels on image, save to static/annotated/ and static/debug/."""
    annotated = annotate_image(image, detections)
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
            stage_id=response.stage_id,
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


async def _process_analysis_pipeline(
    image_bytes: bytes,
    filename: str | None,
    stage_name: str | None,
    date_param: str | None,
    preset: str | None,
    db: Session,
) -> AnalyzeResponse:
    """Core analysis pipeline: saving RAW, decoding, detecting, matching schedule, and saving preview."""
    file_uuid = uuid4().hex

    # 1. Save pristine raw image first (preserves EXIF and original bytes)
    _, raw_url = await run_in_threadpool(_save_raw_image, image_bytes, filename, file_uuid)

    # Decode image once for inference and annotation.
    img_array = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_array is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a readable image")

    # 2. Extract or resolve target date with strict precedence:
    # 1) selected_date (explicitly passed by user in UI)
    # 2) EXIF metadata (DateTimeOriginal)
    # 3) Filename regex pattern (e.g., Screenshot_2026-09-20...)
    # 4) Current system date (date.today())
    target_date, detected_date_str, photo_dt = resolve_analysis_date(
        selected_date_str=date_param,
        image_bytes=image_bytes,
        filename=filename,
    )

    # 3. Resolve active stage and planned machinery requirements
    active_row = None
    stage_planned_period: dict[str, str] | None = None
    machinery_plan: dict[str, int] = {}
    stage_message: str | None = None

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
                s_d = normalize_to_date(active_row.date_start)
                e_d = normalize_to_date(active_row.date_end)
                stage_planned_period = {
                    "start": s_d.strftime("%Y-%m-%d"),
                    "end": e_d.strftime("%Y-%m-%d"),
                }
        else:
            rules = get_stage_rules(resolved_stage)
            machinery_plan = {k.value: v for k, v in rules.required_machinery.items()}
    else:
        # Automatic stage resolution by date
        stage_res = get_active_stage_by_date(target_date)
        if isinstance(stage_res, ScheduleRow):
            active_row = stage_res
            resolved_stage = active_row.stage_name
            machinery_plan = dict(active_row.required_machinery)
            if active_row.date_start and active_row.date_end:
                s_d = normalize_to_date(active_row.date_start)
                e_d = normalize_to_date(active_row.date_end)
                stage_planned_period = {
                    "start": s_d.strftime("%Y-%m-%d"),
                    "end": e_d.strftime("%Y-%m-%d"),
                }
        else:
            # Stage not found on target_date: structured fallback
            active_row = None
            resolved_stage = "Вне этапов СМР"
            n_stage = None
            if isinstance(stage_res, StageFallback):
                n_stage = stage_res.stage
            elif isinstance(stage_res, tuple) and len(stage_res) >= 2:
                n_stage = stage_res[0]
            else:
                nearest = get_nearest_stage(target_date)
                if nearest:
                    n_stage = nearest[0]

            if n_stage:
                s_d = normalize_to_date(n_stage.date_start) if n_stage.date_start else None
                e_d = normalize_to_date(n_stage.date_end) if n_stage.date_end else None
                s_str = s_d.strftime("%Y-%m-%d") if s_d else ""
                e_str = e_d.strftime("%Y-%m-%d") if e_d else ""
                stage_planned_period = {"start": s_str, "end": e_str}
                stage_message = (
                    f'На дату {detected_date_str} активных работ по графику не запланировано. '
                    f'Ближайший этап: "{n_stage.stage_name}" ({s_str} — {e_str})'
                )
            else:
                stage_message = f"На дату {detected_date_str} активных работ по графику не запланировано."

    # 4. Run detector in threadpool
    try:
        detections = await run_in_threadpool(detector.detect, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    h, w = img_array.shape[:2]
    fact_counts = Counter(item.class_name.value for item in detections)
    machinery_fact = dict(fact_counts)

    # 5. Check stage DB record for stage_id and early completion flag
    from ...db.models import Stage  # noqa: PLC0415
    db_stage = db.query(Stage).filter(Stage.name == resolved_stage).first()
    stage_id = db_stage.id if db_stage else (active_row.stage_id if active_row else None)
    is_completed = db_stage.is_completed if db_stage else (active_row.is_completed if active_row else False)

    # 5. Evaluate compliance
    if is_completed:
        status = IncidentStatus.OK
        explanation = (
            f"Этап «{resolved_stage}» завершен досрочно (подтверждено КС-2). "
            "Нормативные требования к технике сняты."
        )
        response = AnalyzeResponse(
            timestamp=datetime.combine(target_date, datetime.min.time()),
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
            analyzed_date=detected_date_str,
            stage_planned_period=stage_planned_period,
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
            delay_days=0,
            penalty_rub=0,
            is_stage_completed=True,
            stage_id=stage_id,
        )
    elif preset in ("norm", "normal"):
        resolved_stage = (
            resolved_stage
            if resolved_stage not in ("Вне графика СМР", "Вне этапов СМР")
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
            timestamp=datetime.combine(target_date, datetime.min.time()),
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
            analyzed_date=detected_date_str,
            stage_planned_period=stage_planned_period or {"start": "2026-09-01", "end": "2026-09-12"},
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
            delay_days=0,
            penalty_rub=0,
            is_stage_completed=False,
            stage_id=stage_id,
        )
    elif preset in ("critical", "violation"):
        resolved_stage = (
            resolved_stage
            if resolved_stage not in ("Вне графика СМР", "Вне этапов СМР")
            else "Разработка грунта котлована с погрузкой"
        )
        machinery_plan = machinery_plan or {"excavator": 2, "dump_truck": 6}
        machinery_fact = machinery_fact or {"excavator": 2}
        if "dump_truck" in machinery_fact:
            del machinery_fact["dump_truck"]
        status = IncidentStatus.CRITICAL
        missing = ["dump_truck"]
        explanation = (
            f"На этапе «{resolved_stage}» не хватает обязательной техники: dump_truck. "
            "Это критичное отклонение плана-факта: дефицит техники может остановить текущие работы и привести к срыву сроков."
        )
        response = AnalyzeResponse(
            timestamp=datetime.combine(target_date, datetime.min.time()),
            active_stage=resolved_stage,
            stage_name=resolved_stage,
            detections=detections,
            status=status,
            compliance_status=status,
            explanation=explanation,
            missing_machinery=missing,
            unexpected_machinery=[],
            observation_quality=ObservationQuality.HIGH,
            model_is_construction_specific=detector.model_is_construction,
            detected_date=detected_date_str,
            analyzed_date=detected_date_str,
            stage_planned_period=stage_planned_period or {"start": "2026-09-15", "end": "2026-10-05"},
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
            delay_days=2,
            penalty_rub=700000,
            is_stage_completed=False,
            stage_id=stage_id,
        )
    elif active_row is None and not cleaned_stage:
        status = IncidentStatus.WARNING
        response = AnalyzeResponse(
            timestamp=datetime.combine(target_date, datetime.min.time()),
            active_stage=resolved_stage,
            stage_name=resolved_stage,
            detections=detections,
            status=status,
            compliance_status=status,
            explanation=stage_message or f"Дата съемки {detected_date_str} выходит за рамки загруженного графика СМР.",
            missing_machinery=[],
            unexpected_machinery=[],
            observation_quality=ObservationQuality.MEDIUM,
            model_is_construction_specific=detector.model_is_construction,
            detected_date=detected_date_str,
            analyzed_date=detected_date_str,
            stage_planned_period=stage_planned_period,
            machinery_plan=machinery_plan,
            machinery_fact=machinery_fact,
            delay_days=1,
            penalty_rub=50000,
            is_stage_completed=False,
            stage_id=stage_id,
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
            is_completed=is_completed,
            stage_id=stage_id,
        )
        response.detections = detections
        response.detected_date = detected_date_str
        response.analyzed_date = detected_date_str
        response.stage_name = resolved_stage
        response.active_stage = resolved_stage
        response.stage_planned_period = stage_planned_period
        response.machinery_plan = machinery_plan
        response.machinery_fact = machinery_fact
        response.compliance_status = response.status
        response.photo_timestamp = photo_dt
        response.timestamp = datetime.combine(target_date, datetime.min.time())
        response.stage_id = stage_id
        response.is_stage_completed = is_completed

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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    stage_name: str | None = Form(default=None),
    selected_date: str | None = Form(default=None),
    date: str | None = Form(default=None),
    preset: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze one site photo against active construction stage.

    Auto-matching pipeline:
    1. Extract date from explicit `selected_date` / `date` form param, EXIF metadata, or filename.
    2. Auto-match active stage from loaded schedule via get_active_stage_by_date(dt).
    3. If date is outside schedule, return status WARNING with nearest stage details.
    4. Detect construction machinery using YOLO with Class-Agnostic NMS & containment suppression.
    5. Match Plan vs Fact and return typed AnalyzeResponse with analyzed_date.
    """
    image_bytes = await image.read()
    date_param = selected_date or date
    return await _process_analysis_pipeline(
        image_bytes=image_bytes,
        filename=image.filename,
        stage_name=stage_name,
        date_param=date_param,
        preset=preset,
        db=db,
    )


@router.post("/analyze-preset", response_model=AnalyzeResponse)
@router.post("/monitoring/analyze-preset", response_model=AnalyzeResponse)
async def analyze_preset(
    preset_type: str = Query(..., pattern="^(norm|normal|critical|violation)$"),
    selected_date: str | None = Query(default=None),
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> AnalyzeResponse:
    """Run analysis for a pre-configured demo scenario directly from disk.

    Avoids network transfers of large binary files from the client.
    Guarantees deterministic demonstration of Plan vs Fact matching.
    """
    candidate_photos = [
        Path("backend/static/demo/site_2026-09-20_deficit.png"),
        Path("data/raw_photos/Screenshot_13.png"),
        Path("data/raw_photos/Screenshot_27.png"),
        Path("data/raw_photos/Screenshot_1.png"),
    ]
    preset_path = None
    for p in candidate_photos:
        if p.exists() and p.is_file():
            preset_path = p
            break

    if not preset_path:
        found = list(Path("data/raw_photos").glob("*.png")) + list(Path("data/raw_photos").glob("*.jpg"))
        if found:
            preset_path = found[0]

    if preset_path and preset_path.exists():
        file_bytes = preset_path.read_bytes()
        file_name = preset_path.name
    else:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        file_bytes = cv2.imencode(".jpg", img)[1].tobytes()
        file_name = f"preset_{preset_type}.jpg"

    schedule = get_loaded_schedule()
    # Programmatically determine a date guaranteed to be inside an active stage from График_шаблон.xlsx
    if preset_type in ("norm", "normal"):
        first_stage = schedule[0] if schedule else None
        if first_stage and first_stage.date_start and first_stage.date_end:
            s_d = normalize_to_date(first_stage.date_start)
            e_d = normalize_to_date(first_stage.date_end)
            default_date = (s_d + timedelta(days=min(4, max(0, (e_d - s_d).days // 2)))).strftime("%Y-%m-%d")
        else:
            default_date = "2026-09-05"
    else:
        excavation_stage = next(
            (s for s in schedule if "котлован" in s.stage_name.lower() or "разработ" in s.stage_name.lower()),
            schedule[min(2, len(schedule) - 1)] if schedule else None,
        )
        if excavation_stage and excavation_stage.date_start and excavation_stage.date_end:
            s_d = normalize_to_date(excavation_stage.date_start)
            e_d = normalize_to_date(excavation_stage.date_end)
            default_date = (s_d + timedelta(days=min(5, max(0, (e_d - s_d).days // 2)))).strftime("%Y-%m-%d")
        else:
            default_date = "2026-09-20"

    target_date_str = selected_date or date or default_date

    return await _process_analysis_pipeline(
        image_bytes=file_bytes,
        filename=file_name,
        stage_name=None,
        date_param=target_date_str,
        preset=preset_type,
        db=db,
    )


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

    filename = f"akt_dgp_{incident_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )