"""Root router for version one endpoints."""

from fastapi import APIRouter

from . import analytics, monitoring, schedule

router = APIRouter(prefix="/api/v1")
router.include_router(monitoring.router)
router.include_router(schedule.router)
router.include_router(analytics.router)