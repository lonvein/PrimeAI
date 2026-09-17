"""Initial SQLAlchemy entities for stages, detections, and alerts."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class Stage(Base):
    """Calendar schedule stage."""

    __tablename__ = "stages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class MachineryDetection(Base):
    """Persisted object detection linked to a stage snapshot."""

    __tablename__ = "machinery_detections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)
    class_name: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[str] = mapped_column(String(32))
    bbox: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IncidentAlert(Base):
    """Explainable plan-versus-fact incident."""

    __tablename__ = "incident_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)