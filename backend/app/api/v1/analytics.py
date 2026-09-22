"""Analytics endpoints — now powered by real persisted data."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.models import IncidentAlert
from ...db.session import get_db
from ...schemas.contracts import AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=AnalyticsSummary)
def summary(db: Session = Depends(get_db)) -> AnalyticsSummary:
    """Return aggregate incident statistics from the database.

    Previously this returned hardcoded zeros. Now it queries real data.
    """
    # Total incidents
    total: int = db.scalar(select(func.count()).select_from(IncidentAlert)) or 0

    # Count by status
    rows = db.execute(
        select(IncidentAlert.status, func.count().label("cnt"))
        .group_by(IncidentAlert.status)
    ).all()
    by_status = {"OK": 0, "WARNING": 0, "CRITICAL": 0}
    for row in rows:
        if row.status in by_status:
            by_status[row.status] = row.cnt

    # 10 most recent incidents for dashboard display
    recent_rows = db.execute(
        select(IncidentAlert)
        .order_by(IncidentAlert.created_at.desc())
        .limit(10)
    ).scalars().all()

    recent = []
    for inc in recent_rows:
        recent.append({
            "id": inc.id,
            "stage_name": inc.stage_name,
            "status": inc.status,
            "explanation": inc.explanation,
            "observation_quality": inc.observation_quality,
            "missing_machinery": json.loads(inc.missing_machinery or "[]"),
            "unexpected_machinery": json.loads(inc.unexpected_machinery or "[]"),
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
        })

    logger.debug("Analytics summary: total=%d  by_status=%s", total, by_status)

    return AnalyticsSummary(
        total_incidents=total,
        by_status=by_status,
        recent_incidents=recent,
    )