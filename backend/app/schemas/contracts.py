"""Typed request and response contracts for construction monitoring."""

from datetime import datetime
from enum import Enum

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


class AnalyzeResponse(BaseModel):
    """Complete result of image detection and stage compliance analysis."""

    timestamp: datetime
    active_stage: str
    detections: list[DetectionItem]
    status: IncidentStatus
    explanation: str
    missing_machinery: list[str]
    unexpected_machinery: list[str]