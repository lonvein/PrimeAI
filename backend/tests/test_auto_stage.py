"""Tests for schedule caching and automatic stage resolution by date."""

from datetime import datetime
from pathlib import Path

import pytest

from backend.app.services.schedule_parser import (
    ensure_default_schedule_loaded,
    get_active_stage_by_date,
    get_loaded_schedule,
    get_schedule_date_range,
)


def test_default_schedule_auto_loaded():
    """Ensure schedule is automatically loaded from Excel template."""
    rows = get_loaded_schedule()
    assert len(rows) >= 7
    # Verify stages have names and required machinery
    first_stage = rows[0]
    assert "снос" in first_stage.stage_name.lower() or "расчист" in first_stage.stage_name.lower()
    assert "excavator" in first_stage.required_machinery
    assert first_stage.required_machinery["excavator"] == 2


def test_schedule_date_range():
    """Check overall schedule start and end dates."""
    start_dt, end_dt = get_schedule_date_range()
    assert start_dt is not None
    assert end_dt is not None
    assert start_dt < end_dt
    assert start_dt.year == 2026
    assert end_dt.year == 2026


def test_active_stage_by_date_early_september():
    """Date 2026-09-05 must map to first excavation/demolition stage."""
    stage = get_active_stage_by_date("2026-09-05")
    assert stage is not None
    assert "Снос" in stage.stage_name or "расчистка" in stage.stage_name
    assert stage.required_machinery.get("excavator") == 2
    assert stage.required_machinery.get("dump_truck") == 4


def test_active_stage_by_date_late_september():
    """Date 2026-09-20 must map to pit excavation stage."""
    stage = get_active_stage_by_date("2026-09-20")
    assert stage is not None
    assert "Разработка грунта котлована" in stage.stage_name
    assert stage.required_machinery.get("excavator") == 2
    assert stage.required_machinery.get("dump_truck") == 6


def test_active_stage_outside_schedule():
    """Date outside schedule bounds must return None."""
    stage_past = get_active_stage_by_date("2025-01-01")
    assert stage_past is None

    stage_future = get_active_stage_by_date("2028-12-31")
    assert stage_future is None
