"""Schedule upload and parsing endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ...schemas.contracts import ScheduleRow, ScheduleUploadResponse
from ...services.schedule_parser import (
    get_active_stages,
    parse_schedule_structured,
    schedule_row_to_stage_requirement,
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

    Optionally determines which stage is active on the given date.
    """
    file_bytes = await file.read()

    try:
        rows: list[ScheduleRow] = parse_schedule_structured(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    """Return the static list of known stage names from the ontology.

    This allows the frontend to populate the stage dropdown without
    requiring a schedule upload.
    """
    from ...services.ontology import STAGE_RULES  # noqa: PLC0415

    return list(STAGE_RULES.keys())