"""Official Moscow DGP Construction Control Incident Act PDF Generator.

Generates a legally structured, formal inspection document:
- Official Moscow Department of Urban Planning Policy (ДГП) header.
- Metadata table (inspection time, camera sector, stage, compliance status).
- Plan vs Fact machinery table comparing schedule requirements against AI detections.
- Embedded annotated site photo with bounding boxes as objective evidence.
- Expert risk conclusion and camera angle assessment (ObservationQuality).
- Signature verification block and digital verification hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..core.config import get_settings
from ..schemas.contracts import MachineryType
from .ontology import get_stage_rules

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font Registration (Guaranteed Cyrillic support)
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False


def _register_cyrillic_fonts() -> tuple[str, str]:
    """Register DejaVuSans and DejaVuSans-Bold fonts for Cyrillic PDF rendering."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "DejaVuSans", "DejaVuSans-Bold"

    base_dir = Path(__file__).resolve().parent.parent
    font_candidates = [
        (base_dir / "assets" / "fonts" / "DejaVuSans.ttf", base_dir / "assets" / "fonts" / "DejaVuSans-Bold.ttf"),
        (Path(".venv/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf"),
         Path(".venv/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf")),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]

    for reg_path, bold_path in font_candidates:
        if reg_path.is_file():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", str(reg_path)))
                if bold_path.is_file():
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold_path)))
                else:
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(reg_path)))
                pdfmetrics.registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold")
                logger.debug("Registered Cyrillic PDF fonts from: %s", reg_path)
                _FONTS_REGISTERED = True
                return "DejaVuSans", "DejaVuSans-Bold"
            except Exception as exc:
                logger.warning("Failed to register font %s: %s", reg_path, exc)

    _FONTS_REGISTERED = True
    return "Helvetica", "Helvetica-Bold"


# Translation table for 8 normative classes into Russian
CLASS_NAMES_RU: dict[str, str] = {
    "dump_truck": "Самосвал",
    "excavator": "Экскаватор",
    "roller": "Каток",
    "manipulator": "Кран-манипулятор",
    "crane_manipulator": "Кран-манипулятор",
    "bulldozer": "Бульдозер",
    "mobile_crane": "Автокран",
    "concrete_mixer": "Автобетоносмеситель",
    "truck": "Грузовик",
}


def generate_incident_act_pdf(
    incident_data: dict[str, Any] | Any,
    image_path: Path | str | None = None,
) -> bytes:
    """Generate official Moscow DGP Construction Control Act as PDF bytes.

    Parameters
    ----------
    incident_data:
        IncidentAlert model or dictionary containing incident details.
    image_path:
        Optional absolute or relative path to the annotated preview image.
    """
    regular_font, bold_font = _register_cyrillic_fonts()

    # Extract fields from model or dict
    if hasattr(incident_data, "id"):
        inc_id = getattr(incident_data, "id", 1) or 1
        stage_name = getattr(incident_data, "stage_name", "") or "Не указан"
        status = getattr(incident_data, "status", "WARNING") or "WARNING"
        explanation = getattr(incident_data, "explanation", "") or ""
        quality = getattr(incident_data, "observation_quality", "MEDIUM") or "MEDIUM"
        missing_raw = getattr(incident_data, "missing_machinery", "[]") or "[]"
        unexpected_raw = getattr(incident_data, "unexpected_machinery", "[]") or "[]"
        created_at = getattr(incident_data, "created_at", None)
        ann_path_db = getattr(incident_data, "annotated_image_path", None)
    else:
        inc_id = incident_data.get("id", 1)
        stage_name = incident_data.get("stage_name", "Не указан")
        status = incident_data.get("status", "WARNING")
        explanation = incident_data.get("explanation", "")
        quality = incident_data.get("observation_quality", "MEDIUM")
        missing_raw = incident_data.get("missing_machinery", [])
        unexpected_raw = incident_data.get("unexpected_machinery", [])
        created_at = incident_data.get("created_at")
        ann_path_db = incident_data.get("annotated_image_path")

    # Parse JSON if string
    missing_list: list[str] = json.loads(missing_raw) if isinstance(missing_raw, str) else list(missing_raw)
    unexpected_list: list[str] = json.loads(unexpected_raw) if isinstance(unexpected_raw, str) else list(unexpected_raw)

    # Date formatting
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%d.%m.%Y %H:%M:%S MSK")
    elif isinstance(created_at, str):
        date_str = created_at[:19].replace("T", " ")
    else:
        date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")

    # Resolve physical image path
    settings = get_settings()
    resolved_img_path: Path | None = None
    if image_path:
        p = Path(image_path)
        if p.is_file():
            resolved_img_path = p
        elif (settings.static_dir / p).is_file():
            resolved_img_path = settings.static_dir / p

    if not resolved_img_path and ann_path_db:
        # e.g. /static/annotated/xyz.jpg -> backend/static/annotated/xyz.jpg
        clean = ann_path_db.lstrip("/").replace("static/", "")
        candidate = settings.static_dir / clean
        if candidate.is_file():
            resolved_img_path = candidate

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=28,
    )

    # Styles
    title_style = ParagraphStyle(
        "DGPTitle",
        fontName=bold_font,
        fontSize=11,
        leading=14,
        alignment=1,  # Center
        textColor=colors.HexColor("#0A2540"),
    )
    subtitle_style = ParagraphStyle(
        "DGPSubtitle",
        fontName=bold_font,
        fontSize=13,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#B71C1C") if status == "CRITICAL" else colors.HexColor("#D35400"),
    )
    system_sub_style = ParagraphStyle(
        "DGPSystem",
        fontName=regular_font,
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#555555"),
    )
    section_h2 = ParagraphStyle(
        "DGPSectionH2",
        fontName=bold_font,
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#0A2540"),
        spaceBefore=6,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "DGPBody",
        fontName=regular_font,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#222222"),
    )
    bold_body = ParagraphStyle(
        "DGPBoldBody",
        fontName=bold_font,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#222222"),
    )
    table_cell = ParagraphStyle(
        "DGPTableCell",
        fontName=regular_font,
        fontSize=8,
        leading=10,
    )
    table_header = ParagraphStyle(
        "DGPTableHeader",
        fontName=bold_font,
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    story = []

    # 1. Official Header
    story.append(Paragraph("ПРАВИТЕЛЬСТВО МОСКВЫ", system_sub_style))
    story.append(Paragraph("ДЕПАРТАМЕНТ ГРАДОСТРОИТЕЛЬНОЙ ПОЛИТИКИ ГОРОДА МОСКВЫ", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"АКТ ФИКСАЦИИ ОТКЛОНЕНИЙ КАЛЕНДАРНОГО ПЛАНА СМР № {inc_id}", subtitle_style))
    story.append(Paragraph("Единая автоматизированная система объективного контроля «Build Eye AI»", system_sub_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0A2540"), spaceAfter=6))

    # 2. Metadata Grid
    status_ru = {
        "CRITICAL": "КРИТИЧЕСКОЕ ОТКЛОНЕНИЕ (Срыв сроков)",
        "WARNING": "ТРЕБУЕТ ВНИМАНИЯ (Предупреждение)",
        "OK": "СООТВЕТСТВУЕТ НОРМАТИВУ",
    }.get(status, status)

    quality_ru = {
        "HIGH": "Высокое (детальный план площадки)",
        "MEDIUM": "Среднее (достаточная видимость)",
        "LOW": "Ограниченное (дальний план / 20+ этаж)",
    }.get(quality, quality)

    meta_data = [
        [
            Paragraph("<b>Дата и время фиксации:</b>", body_style),
            Paragraph(date_str, body_style),
            Paragraph("<b>Объект / Активный этап:</b>", body_style),
            Paragraph(f"<b>{stage_name}</b>", body_style),
        ],
        [
            Paragraph("<b>Статус контроля:</b>", body_style),
            Paragraph(
                f"<font color='{'#b71c1c' if status == 'CRITICAL' else '#d35400'}'><b>{status_ru}</b></font>",
                body_style,
            ),
            Paragraph("<b>Качество ракурса:</b>", body_style),
            Paragraph(quality_ru, body_style),
        ],
        [
            Paragraph("<b>Сектор наблюдения:</b>", body_style),
            Paragraph("Камера №1 (Въездная группа / Периметр)", body_style),
            Paragraph("<b>Основание проверки:</b>", body_style),
            Paragraph("Календарный график ДГП (ППР)", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[120, 140, 120, 140])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CED4DA")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E9ECEF")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # 3. Plan vs Fact Table
    story.append(Paragraph("1. Сравнительный анализ: Нормативный план vs Фактическое наличие техники", section_h2))

    plan_table_data = [
        [
            Paragraph("Нормативная строительная техника", table_header),
            Paragraph("Требуется (План)", table_header),
            Paragraph("Фактически (ИИ)", table_header),
            Paragraph("Оценка соответствия", table_header),
        ]
    ]

    rules = get_stage_rules(stage_name)
    required_specs = rules.required_machinery if rules else {}

    # Rows for required machinery
    for m_type, req_qty in required_specs.items():
        m_name = m_type.value if hasattr(m_type, "value") else str(m_type)
        m_ru = CLASS_NAMES_RU.get(m_name, m_name)
        is_missing = m_name in missing_list
        fact_qty = "0 ед." if is_missing else f"{req_qty} ед."
        if is_missing:
            verdict = "<font color='#b71c1c'><b>Отсутствует (Дефицит)</b></font>"
        else:
            verdict = "<font color='#2b8a5a'><b>Соответствует норме</b></font>"

        plan_table_data.append([
            Paragraph(f"<b>{m_ru}</b> ({m_name})", table_cell),
            Paragraph(f"{req_qty} ед.", table_cell),
            Paragraph(fact_qty, table_cell),
            Paragraph(verdict, table_cell),
        ])

    # Rows for unexpected machinery
    for unexp in unexpected_list:
        unexp_ru = CLASS_NAMES_RU.get(unexp, unexp)
        plan_table_data.append([
            Paragraph(f"<b>{unexp_ru}</b> ({unexp})", table_cell),
            Paragraph("0 ед. (вне плана)", table_cell),
            Paragraph("1+ ед.", table_cell),
            Paragraph("<font color='#d35400'>Нетипичная техника</font>", table_cell),
        ])

    if len(plan_table_data) == 1:
        plan_table_data.append([
            Paragraph("Нормативные требования для этапа не заданы", table_cell),
            Paragraph("-", table_cell),
            Paragraph("-", table_cell),
            Paragraph("Требуется уточнение графика", table_cell),
        ])

    ptable = Table(plan_table_data, colWidths=[180, 100, 100, 140])
    ptable.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A2540")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CED4DA")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E9ECEF")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    story.append(ptable)
    story.append(Spacer(1, 6))

    # 4. Embedded Photo (Evidence Base)
    story.append(Paragraph("2. Материалы фотофиксации (Доказательная база с ИИ-разметкой)", section_h2))

    if resolved_img_path and resolved_img_path.is_file():
        try:
            with PILImage.open(resolved_img_path) as pil_img:
                img_w, img_h = pil_img.size
            max_w, max_h = 520, 200
            scale = min(max_w / img_w, max_h / img_h, 1.0)
            target_w = img_w * scale
            target_h = img_h * scale

            img_flow = RLImage(str(resolved_img_path), width=target_w, height=target_h)
            img_table = Table([[img_flow]], colWidths=[520])
            img_table.setStyle(
                TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0A2540")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ])
            )
            story.append(img_table)
            story.append(
                Paragraph(
                    "<i>Кадр объективного контроля с детектированными единицами техники и ограничивающими рамками (YOLO Class-Agnostic NMS).</i>",
                    system_sub_style,
                )
            )
        except Exception as exc:
            logger.warning("Could not embed image into PDF: %s", exc)
            story.append(Paragraph("<i>[Изображение фотофиксации временно недоступно]</i>", body_style))
    else:
        story.append(
            Paragraph(
                "<i>Фотофиксация: кадр сохранен в цифровом архиве ДГП и доступен по идентификатору события.</i>",
                body_style,
            )
        )

    story.append(Spacer(1, 6))

    # 5. Conclusion & Recommendations
    story.append(Paragraph("3. Заключение инспекции и анализ рисков", section_h2))
    story.append(Paragraph(explanation, body_style))

    if quality == "LOW":
        story.append(Spacer(1, 3))
        low_notice = [
            [
                Paragraph(
                    "<b>⚠️ ВНИМАНИЕ ИНСПЕКТОРА ДГП (ОСОБЫЙ РАКУРС):</b><br/>"
                    "Качество ракурса наблюдения определено как LOW (дальний план / острый угол съемки с верхнего яруса). "
                    "В соответствии с регламентом ДГП Москвы, статус зафиксирован как ПРЕДУПРЕЖДЕНИЕ. "
                    "Рекомендуется скорректировать угол наклона стационарной камеры или запросить подтверждающий снимок "
                    "с секторной камеры въезда №2 перед вынесением штрафных санкций.",
                    body_style,
                )
            ]
        ]
        low_table = Table(low_notice, colWidths=[520])
        low_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3CD")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FFEBAA")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(low_table)

    story.append(Spacer(1, 8))

    # 6. Signatures and Verification Block
    story.append(Paragraph("4. Подписи сторон и электронная верификация", section_h2))

    sig_data = [
        [
            Paragraph("<b>Инспектор строительного контроля<br/>ДГП города Москвы:</b>", body_style),
            Paragraph("<b>Ответственный представитель<br/>технадзора генерального подрядчика:</b>", body_style),
        ],
        [
            Paragraph("__________________ / __________________ /", bold_body),
            Paragraph("__________________ / __________________ /", bold_body),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[260, 260])
    sig_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(sig_table)

    # Verification digital hash
    content_hash = hashlib.sha256(f"{inc_id}-{stage_name}-{status}-{date_str}".encode()).hexdigest()
    story.append(
        Paragraph(
            f"Цифровой хеш верификации акта Build Eye AI (SHA-256): <b>{content_hash}</b>",
            system_sub_style,
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
