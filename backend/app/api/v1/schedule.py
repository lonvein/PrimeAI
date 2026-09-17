"""Schedule upload and parsing endpoints."""

from fastapi import APIRouter, File, UploadFile

from ...services.schedule_parser import parse_schedule

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/upload")
async def upload_schedule(file: UploadFile = File(...)) -> dict:
    """Parse an uploaded Excel schedule and return normalized rows."""

    return {"filename": file.filename, "rows": parse_schedule(await file.read())}