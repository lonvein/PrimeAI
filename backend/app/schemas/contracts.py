"""Typed request and response contracts for construction monitoring."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MachineryType(str, Enum):
    """Supported construction machinery classes (8 target classes of DGP Moscow)."""

    EXCAVATOR = "excavator"
    DUMP_TRUCK = "dump_truck"
    BULLDOZER = "bulldozer"
    CONCRETE_MIXER = "concrete_mixer"
    MOBILE_CRANE = "mobile_crane"
    MANIPULATOR = "manipulator"
    CRANE_MANIPULATOR = "manipulator"
    ROLLER = "roller"
    TRUCK = "truck"

    @classmethod
    def _missing_(cls, value: object) -> "MachineryType | None":
        if isinstance(value, str):
            normalized = value.casefold().strip().replace("-", "_").replace(" ", "_")
            if normalized in ("crane_manipulator", "кран_манипулятор", "манипулятор"):
                return cls.MANIPULATOR
        return None


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

    HIGH   — real model loaded, reliable camera angle and coverage.
    MEDIUM — real model loaded, average scene quality.
    LOW    — distant camera angle / top-down view (<2% box area) or synthetic fallback.
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
    # Observation quality: HIGH, MEDIUM, LOW
    observation_quality: ObservationQuality = ObservationQuality.MEDIUM
    # Specific camera angle recommendation when quality is LOW
    camera_recommendation: str | None = None
    # Model indicator
    model_is_construction_specific: bool = False
    # Persisted incident ID in DB for 1-click PDF Act generation
    incident_id: int | None = None
    # URLs for raw unmodified photo and annotated preview photo:
    raw_image_url: str | None = None
    annotated_image_url: str | None = None
    image_url: str | None = None  # alias for annotated_image_url
    # Backward compatibility:
    debug_image_url: str | None = None
    # Extracted timestamp from photo EXIF metadata or filename (if available).
    photo_timestamp: datetime | None = None
    # Date auto-detected or specified (YYYY-MM-DD)
    detected_date: str | None = None
    # Active stage name (synced with active_stage)
    stage_name: str | None = None
    # Planned period for active stage {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    stage_planned_period: dict[str, str] | None = None
    # Normative machinery requirements from schedule {machinery_type: required_count}
    machinery_plan: dict[str, int] = Field(default_factory=dict)
    # Actually detected machinery counts {machinery_type: detected_count}
    machinery_fact: dict[str, int] = Field(default_factory=dict)
    # Compliance status alias (OK, WARNING, CRITICAL)
    compliance_status: IncidentStatus | None = None


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