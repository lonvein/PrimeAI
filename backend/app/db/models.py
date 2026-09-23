"""SQLAlchemy ORM entities for stages, detections, and alerts.

Changes from initial version:
- confidence stored as Float (was incorrectly String)
- bbox stored as Text (JSON array string)
- created_at uses timezone-aware UTC (was naive utcnow, deprecated in Python 3.12)
- Added observation_quality column to IncidentAlert
- Added stage_name denormalized to IncidentAlert for direct query without JOIN
"""

import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


def _utcnow() -> datetime:
    """Return timezone-aware current UTC time (replaces deprecated utcnow)."""
    return datetime.now(timezone.utc)


class Stage(Base):
    """Calendar schedule stage loaded from the uploaded Excel file."""

    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Optional: date range from the schedule
    date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Raw text of normative machinery plan from Excel
    machinery_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    detections: Mapped[list["MachineryDetection"]] = relationship(
        "MachineryDetection", back_populates="stage", lazy="select"
    )
    incidents: Mapped[list["IncidentAlert"]] = relationship(
        "IncidentAlert", back_populates="stage", lazy="select"
    )


class MachineryDetection(Base):
    """Persisted object detection linked to a stage snapshot."""

    __tablename__ = "machinery_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # nullable FK — detection might not be linked to a stage (e.g. unknown stage)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)
    class_name: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)  # was String, now correct Float
    bbox: Mapped[str] = mapped_column(Text)  # JSON: "[x1, y1, x2, y2]"
    raw_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    stage: Mapped["Stage | None"] = relationship("Stage", back_populates="detections")

    @classmethod
    def from_detection_item(
        cls,
        item,
        stage_id: int | None = None,
        raw_image_path: str | None = None,
        annotated_image_path: str | None = None,
    ) -> "MachineryDetection":
        """Create from a DetectionItem schema object."""
        return cls(
            stage_id=stage_id,
            class_name=item.class_name.value,
            confidence=item.confidence,
            bbox=json.dumps([round(v, 1) for v in item.bbox]),
            raw_image_path=raw_image_path,
            annotated_image_path=annotated_image_path,
        )


class IncidentAlert(Base):
    """Explainable plan-versus-fact incident record."""

    __tablename__ = "incident_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)
    # Denormalized stage name for easy querying without JOIN.
    stage_name: Mapped[str] = mapped_column(String(512), index=True, default="")
    status: Mapped[str] = mapped_column(String(16), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    observation_quality: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    # JSON list of missing machinery names
    missing_machinery: Mapped[str] = mapped_column(Text, default="[]")
    # JSON list of unexpected machinery names
    unexpected_machinery: Mapped[str] = mapped_column(Text, default="[]")
    raw_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    stage: Mapped["Stage | None"] = relationship("Stage", back_populates="incidents")