"""Typed request and response contracts for construction monitoring."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MachineryType(str, Enum):
    """Supported construction machinery classes."""

    EXCAVATOR = "excavator"
    DUMP_TRUCK = "dump_truck"
    BULLDOZER = "bulldozer"
    CONCRETE_MIXER = "concrete_mixer"
    MOBILE_CRANE = "mobile_crane"
    CRANE_MANIPULATOR = "crane_manipulator"
    ROLLER = "roller"
    TRUCK = "truck"


class DetectionItem(BaseModel):
    """One object detected on a construction site image."""

    class_name: MachineryType
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[float] = Field(min_length=4, max_length=4)


class StageRequirement(BaseModel):
    """Normative machinery requirements for one construction stage."""

    stage_name: str
    required_machinery: dict[MachineryType, int] = Field(default_factory=dict)
    optional_machinery: list[MachineryType] = Field(default_factory=list)


class IncidentStatus(str, Enum):
    """Compliance status produced by the matching engine."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ObservationQuality(str, Enum):
    """How reliable is the detection result for compliance judgement.

    HIGH   — real model loaded, multiple detections found.
    MEDIUM — real model loaded, but no domain classes detected
             (model may be pre-COCO; absence does not mean violation).
    LOW    — synthetic fallback active (weights missing).
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalyzeResponse(BaseModel):
    """Complete result of image detection and stage compliance analysis."""

    timestamp: datetime
    active_stage: str
    detections: list[DetectionItem]
    status: IncidentStatus
    explanation: str
    missing_machinery: list[str]
    unexpected_machinery: list[str]
    # NEW: tells the frontend (and the user) how reliable the result is.
    observation_quality: ObservationQuality = ObservationQuality.MEDIUM
    # NEW: indicates whether the model is fine-tuned for construction or generic COCO.
    model_is_construction_specific: bool = False
    # URLs for raw unmodified photo and annotated preview photo:
    raw_image_url: str | None = None
    annotated_image_url: str | None = None
    image_url: str | None = None  # alias for annotated_image_url
    # Backward compatibility:
    debug_image_url: str | None = None
    # NEW: extracted timestamp from photo EXIF metadata or filename (if available).
    photo_timestamp: datetime | None = None


class BatchAnalyzeResponse(BaseModel):
    """Result of batch multi-photo analysis with aggregated site-level compliance.

    Aggregates detections across multiple camera angles/sectors to solve
    the partial observability problem (limited camera field of view).
    """

    total_images: int
    active_stage: str
    overall_status: IncidentStatus
    overall_explanation: str
    overall_quality: ObservationQuality
    total_detections_count: int
    machinery_summary: dict[str, int]
    missing_machinery: list[str]
    unexpected_machinery: list[str]
    items: list[AnalyzeResponse]


class ScheduleRow(BaseModel):
    """One row from the uploaded Excel schedule."""

    index: int
    stage_name: str
    zone: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    days: int | None = None
    machinery_plan: str | None = None  # raw text from Excel
    required_machinery: dict[str, int] = Field(default_factory=dict)  # parsed
    contractor: str | None = None


class ScheduleUploadResponse(BaseModel):
    """Response for schedule upload endpoint."""

    filename: str
    rows: list[ScheduleRow]
    active_stage: ScheduleRow | None = None  # stage active as of query date


class AnalyticsSummary(BaseModel):
    """Real analytics summary derived from persisted incidents."""

    total_incidents: int
    by_status: dict[str, int]
    recent_incidents: list[dict[str, Any]] = Field(default_factory=list)