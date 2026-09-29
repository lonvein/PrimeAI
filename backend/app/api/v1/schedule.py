"""Schedule upload and parsing endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.contracts import ScheduleRow, ScheduleUploadResponse
from ...services.ontology import get_all_stage_names, load_schedule_rules
from ...services.schedule_parser import (
    get_active_stages,
    get_loaded_schedule,
    parse_schedule_structured,
    set_loaded_schedule,
    toggle_stage_completion,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=ScheduleUploadResponse)
async def upload_schedule(
    file: UploadFile = File(...),
    query_date: str | None = Query(
        default=None,
        description="ISO date (YYYY-MM-DD) to find which stage is active. "
                    "Defaults to today.",
    ),
) -> ScheduleUploadResponse:
    """Parse an uploaded Excel schedule and return structured stage data.

    Side effect: updates the ontology with schedule-derived machinery rules
    so that subsequent /analyze calls use the uploaded normative requirements.
    """
    file_bytes = await file.read()

    try:
        rows: list[ScheduleRow] = parse_schedule_structured(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Load schedule rows into in-memory cache and ontology
    set_loaded_schedule(rows)
    loaded_count = len(rows)
    logger.info("Loaded %d schedule-derived rules into ontology.", loaded_count)

    # Determine active stage for the requested date.
    if query_date:
        try:
            target_dt = datetime.fromisoformat(query_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {query_date!r}. Use YYYY-MM-DD.",
            )
    else:
        target_dt = datetime.now()

    active = get_active_stages(rows, target_dt)
    # When multiple stages overlap, prefer the one that started most recently.
    active_stage: ScheduleRow | None = (
        max(active, key=lambda r: r.date_start or datetime.min)
        if active
        else None
    )

    logger.info(
        "Schedule uploaded: %d stages, active on %s: %s",
        len(rows),
        target_dt.date(),
        active_stage.stage_name if active_stage else "none",
    )

    return ScheduleUploadResponse(
        filename=file.filename or "schedule.xlsx",
        rows=rows,
        active_stage=active_stage,
    )


@router.get("/stages", response_model=list[str])
async def list_stages() -> list[str]:
    """Return combined list of known stage names from schedule + static ontology.

    If a schedule has been uploaded, its stages appear first.
    """
    return get_all_stage_names()


@router.get("/stages/details", response_model=list[ScheduleRow])
async def list_stages_details() -> list[ScheduleRow]:
    """Return full list of loaded ScheduleRows including stage_id and is_completed."""
    return get_loaded_schedule()


@router.patch("/stages/{stage_id}/toggle-completed")
async def toggle_stage_completed(
    stage_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Toggle the is_completed flag for a stage in SQLite DB and memory cache."""
    try:
        sid, is_completed, stage_name = toggle_stage_completion(stage_id, db)
        return {
            "stage_id": sid,
            "is_completed": is_completed,
            "stage_name": stage_name,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Error toggling stage %d completion: %s", stage_id, exc)
        raise HTTPException(status_code=500, detail="Internal database error") from exc