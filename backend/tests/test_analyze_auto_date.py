"""Tests for POST /analyze auto-matching by date without mandatory stage_name."""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _make_dummy_image_bytes() -> bytes:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", img)
    return encoded.tobytes()


def test_analyze_auto_stage_from_filename():
    """Omitting stage_name must extract date from filename and resolve active stage."""
    file_bytes = _make_dummy_image_bytes()
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("site_2026-09-05_drone.png", file_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["detected_date"] == "2026-09-05"
    assert "снос" in data["stage_name"].lower() or "расчист" in data["stage_name"].lower()
    assert data["stage_planned_period"] is not None
    assert "start" in data["stage_planned_period"]
    assert "end" in data["stage_planned_period"]
    assert data["machinery_plan"] == {"excavator": 2, "dump_truck": 4}
    assert isinstance(data["machinery_fact"], dict)
    assert data["compliance_status"] in ("OK", "WARNING", "CRITICAL")


def test_analyze_explicit_date_form_param():
    """Explicit date parameter must override or supply date for stage matching."""
    file_bytes = _make_dummy_image_bytes()
    response = client.post(
        "/api/v1/analyze",
        data={"date": "2026-09-20"},
        files={"image": ("unnamed_photo.png", file_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["detected_date"] == "2026-09-20"
    assert "котлован" in data["stage_name"].lower()
    assert data["machinery_plan"] == {"excavator": 2, "dump_truck": 6}


def test_analyze_date_outside_schedule_returns_warning():
    """Date outside schedule bounds must return status WARNING with exact DGP wording."""
    file_bytes = _make_dummy_image_bytes()
    response = client.post(
        "/api/v1/analyze",
        data={"date": "2028-06-15"},
        files={"image": ("future_photo.png", file_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["compliance_status"] == "WARNING"
    assert data["status"] == "WARNING"
    assert data["stage_name"] in ("Вне графика СМР", "Вне этапов СМР")
    assert "2028-06-15" in data["explanation"]
    assert "активных работ по графику не запланировано" in data["explanation"]
    assert "Ближайший этап:" in data["explanation"]
    assert data["analyzed_date"] == "2028-06-15"


def test_analyze_preset_normal_without_date_returns_real_stage():
    """Calling /analyze-preset?preset_type=normal must return real stage name and HTTP 200."""
    response = client.post("/api/v1/analyze-preset?preset_type=normal")
    assert response.status_code == 200
    data = response.json()
    assert data["stage_name"] is not None
    assert data["stage_name"] != "Вне этапов СМР"
    assert "снос" in data["stage_name"].lower() or "расчист" in data["stage_name"].lower()
    assert data["compliance_status"] == "OK"
    assert data["analyzed_date"] == "2026-09-05"


def test_analyze_russian_date_format_normalized():
    """Passing selected_date='05.09.2026' must return analyzed_date='2026-09-05'."""
    file_bytes = _make_dummy_image_bytes()
    response = client.post(
        "/api/v1/analyze",
        data={"selected_date": "05.09.2026"},
        files={"image": ("photo.png", file_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analyzed_date"] == "2026-09-05"
    assert "снос" in data["stage_name"].lower() or "расчист" in data["stage_name"].lower()
    assert data["stage_planned_period"] == {"start": "2026-09-01", "end": "2026-09-12"}


def test_analyze_preset_endpoint_norm():
    """Test POST /api/v1/analyze-preset with preset_type=norm."""
    response = client.post(
        "/api/v1/analyze-preset?preset_type=norm&selected_date=2026-09-05"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    assert data["compliance_status"] == "OK"
    assert data["analyzed_date"] == "2026-09-05"
    assert data["raw_image_url"] is not None
    assert data["annotated_image_url"] is not None
    assert "снос" in data["stage_name"].lower() or "расчист" in data["stage_name"].lower()


def test_analyze_preset_endpoint_critical():
    """Test POST /api/v1/analyze-preset with preset_type=critical."""
    response = client.post(
        "/api/v1/analyze-preset?preset_type=critical&selected_date=2026-09-20"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CRITICAL"
    assert data["compliance_status"] == "CRITICAL"
    assert data["analyzed_date"] == "2026-09-20"
    assert "dump_truck" in data["missing_machinery"]


def test_analyze_selected_date_priority():
    """selected_date must take priority over date parameter."""
    file_bytes = _make_dummy_image_bytes()
    response = client.post(
        "/api/v1/analyze",
        data={"selected_date": "2026-09-05", "date": "2026-09-20"},
        files={"image": ("site_2026-09-20.png", file_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analyzed_date"] == "2026-09-05"
    assert "снос" in data["stage_name"].lower() or "расчист" in data["stage_name"].lower()


def test_presets_endpoint():
    """Check demo presets endpoint."""
    res = client.get("/api/v1/monitoring/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) >= 2
    ids = [p["id"] for p in presets]
    assert "norm" in ids
    assert "critical" in ids

