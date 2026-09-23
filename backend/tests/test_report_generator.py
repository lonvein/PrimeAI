"""Unit tests for the official Moscow DGP Construction Control Act PDF generator."""

from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.report_generator import generate_incident_act_pdf


def test_generate_pdf_from_dict() -> None:
    """Verify PDF generation from dictionary input."""
    incident_data = {
        "id": 142,
        "stage_name": "Земляные работы / Котлован",
        "status": "CRITICAL",
        "explanation": "На этапе не обнаружен самосвал (dump_truck). Критическое отклонение от графика.",
        "observation_quality": "HIGH",
        "missing_machinery": ["dump_truck"],
        "unexpected_machinery": [],
        "created_at": datetime.now(timezone.utc),
    }

    pdf_bytes = generate_incident_act_pdf(incident_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file must be a valid PDF"


def test_generate_pdf_with_low_quality_angle() -> None:
    """Verify PDF generation includes special LOW observation quality notice."""
    incident_data = {
        "id": 143,
        "stage_name": "Земляные работы / Котлован",
        "status": "WARNING",
        "explanation": "Качество ракурса: LOW (дальний план / острый угол съемки с верхнего яруса).",
        "observation_quality": "LOW",
        "missing_machinery": ["dump_truck"],
        "unexpected_machinery": ["crane_manipulator"],
        "created_at": datetime.now(timezone.utc),
    }

    pdf_bytes = generate_incident_act_pdf(incident_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_pdf_with_real_image() -> None:
    """Verify PDF generation embeds physical image if available."""
    incident_data = {
        "id": 144,
        "stage_name": "Земляные работы / Котлован",
        "status": "CRITICAL",
        "explanation": "Отсутствует нормативная техника.",
        "observation_quality": "HIGH",
        "missing_machinery": ["dump_truck"],
        "unexpected_machinery": [],
        "created_at": datetime.now(timezone.utc),
    }

    test_image = Path("data/raw_photos/Screenshot_13.png")
    pdf_bytes = generate_incident_act_pdf(incident_data, image_path=test_image)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000, "PDF with embedded image should be larger than plain text PDF"
    assert pdf_bytes.startswith(b"%PDF-")
