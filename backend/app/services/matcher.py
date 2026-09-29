"""Explainable plan-versus-fact machinery compliance matching.

IMPORTANT: Observation semantics.

A single photograph covers a limited field of view. Absence of machinery
in one photo does NOT prove absence on the construction site. Therefore:

- If detector returned detections (real model, found something):
    → standard compliance logic applies.
- If detector found nothing with a real model:
    → status is WARNING (not CRITICAL): "not observed, cannot confirm".
    → observation_quality = MEDIUM.
- If detector is synthetic fallback (weights missing):
    → status is WARNING: "cannot assess, model not loaded".
    → observation_quality = LOW.
- If required machinery IS observed:
    → status is OK.
    → observation_quality = HIGH.
- If unexpected machinery is observed:
    → status is WARNING (potential misuse of resources).
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from ..schemas.contracts import (
    AnalyzeResponse,
    IncidentStatus,
    MachineryType,
    ObservationQuality,
)
from .ontology import get_stage_rules

logger = logging.getLogger(__name__)

# Confidence below which a detection is treated as unreliable.
# Synthetic fallback uses 0.01 — far below this threshold.
SYNTHETIC_CONFIDENCE_THRESHOLD = 0.05


def evaluate_compliance(
    stage_name: str,
    detected_classes: list[str],
    *,
    detections: list[DetectionItem] | None = None,
    image_shape: tuple[int, int] | None = None,
    model_is_real: bool = True,
    model_is_construction: bool = True,
    is_completed: bool = False,
    stage_id: int | None = None,
) -> AnalyzeResponse:
    """Compare detected machinery counts with the active stage requirements.

    Parameters
    ----------
    stage_name:
        Name of the construction stage (matched against ontology).
    detected_classes:
        List of MachineryType value strings returned by the detector.
    detections:
        Optional list of DetectionItem objects for bounding-box geometry analysis.
    image_shape:
        Optional (height, width) of the image for relative area calculation.
    model_is_real:
        False when synthetic fallback is active (no weights loaded).
    model_is_construction:
        True only when weights are fine-tuned on construction machinery.
        When False (generic COCO model), absence of classes is downgraded
        from CRITICAL to WARNING because the model cannot reliably detect
        most construction equipment.
    """
    rules = get_stage_rules(stage_name)

    # --- Normalise detected class strings to MachineryType enum values ---
    normalized: list[MachineryType] = []
    for class_name in detected_classes:
        try:
            normalized.append(MachineryType(class_name.casefold().strip()))
        except ValueError:
            logger.debug("Ignoring unknown class in compliance check: %r", class_name)
            continue

    counts = Counter(normalized)

    # --- Compute missing and unexpected ---
    missing = [
        machinery.value
        for machinery, required_count in rules.required_machinery.items()
        if counts[machinery] < required_count
    ]
    unexpected = [
        machinery.value
        for machinery in sorted(set(normalized), key=lambda m: m.value)
        if machinery not in rules.required_machinery
        and machinery not in rules.optional_machinery
    ]

    # --- Evaluate camera angle geometry (relative bounding-box area) ---
    camera_recommendation: str | None = None
    avg_rel_area: float | None = None
    if detections and image_shape:
        height, width = image_shape
        frame_area = max(1.0, float(height * width))
        rel_areas = [
            max(0.0, (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1])) / frame_area
            for d in detections
        ]
        if rel_areas:
            avg_rel_area = sum(rel_areas) / len(rel_areas)

    # --- Determine observation quality ---
    if not model_is_real:
        observation_quality = ObservationQuality.LOW
    elif avg_rel_area is not None and avg_rel_area < 0.02:
        # Distance > 80m or high-altitude / steep perspective from 20th floor:
        observation_quality = ObservationQuality.LOW
        camera_recommendation = (
            "Качество ракурса: LOW (дальний план / острый угол съемки с верхнего яруса). "
            "Рекомендуется скорректировать угол наклона или переключиться на секторную камеру въезда №2."
        )
    elif missing and not model_is_construction:
        # Generic COCO model cannot see most construction classes.
        # Absence in photo ≠ absence on site.
        observation_quality = ObservationQuality.MEDIUM
    elif normalized:
        observation_quality = ObservationQuality.HIGH
    else:
        observation_quality = ObservationQuality.MEDIUM

    # --- Determine status and explanation ---
    if is_completed:
        status = IncidentStatus.OK
        delay_days = 0
        penalty_rub = 0
        explanation = (
            f"Этап «{rules.stage_name}» завершен досрочно (подтверждено КС-2). "
            "Нормативные требования к технике сняты."
        )
        missing = []
        unexpected = []
    elif not model_is_real:
        # Synthetic fallback — cannot make any real assessment.
        status = IncidentStatus.WARNING
        explanation = (
            f"Модель детекции не загружена (отсутствуют веса). "
            f"Оценка соответствия для этапа «{rules.stage_name}» невозможна. "
            "Загрузите файл весов YOLO для реального анализа."
        )
    elif not rules.required_machinery:
        # Stage not in ontology.
        status = IncidentStatus.WARNING
        explanation = (
            f"Этап «{rules.stage_name}» не найден в нормативном справочнике. "
            "Автоматическое подтверждение соответствия невозможно; добавьте правило этапа."
        )
    elif missing and observation_quality == ObservationQuality.LOW:
        # Low camera quality — do NOT penalize with CRITICAL!
        status = IncidentStatus.WARNING
        rec_text = camera_recommendation or "Рекомендуется скорректировать ракурс съемки."
        explanation = (
            f"На этапе «{rules.stage_name}» зафиксирован возможный дефицит техники: {', '.join(missing)}. "
            f"{rec_text} Во избежание ложного штрафа статус зафиксирован как ПРЕДУПРЕЖДЕНИЕ (WARNING) "
            "до проведения перепроверки с секторной камеры."
        )
    elif missing and model_is_construction:
        # Fine-tuned model + machinery missing = CRITICAL.
        status = IncidentStatus.CRITICAL
        explanation = (
            f"На этапе «{rules.stage_name}» не хватает обязательной техники: "
            f"{', '.join(missing)}. Это критичное отклонение плана-факта: "
            "дефицит техники может остановить текущие работы и привести к срыву сроков."
        )
    elif missing and not model_is_construction:
        # Generic COCO model — cannot detect most construction classes.
        observed_str = (
            f"На снимке обнаружено: {', '.join(c.value for c in normalized)}."
            if normalized
            else "На снимке техника не обнаружена."
        )
        status = IncidentStatus.WARNING
        explanation = (
            f"Этап «{rules.stage_name}»: нормативная техника ({', '.join(missing)}) "
            f"не зафиксирована на данном снимке. {observed_str} "
            "Используется базовая модель (COCO), которая не обучена на строительной технике. "
            "Отсутствие детекции не означает физического отсутствия техники на площадке. "
            "Для точного анализа необходима дообученная модель."
        )
    elif unexpected:
        status = IncidentStatus.WARNING
        explanation = (
            f"Обязательная техника для этапа «{rules.stage_name}» обнаружена, "
            f"но присутствует нетипичная техника: {', '.join(unexpected)}. "
            "Проверьте расстановку техники и риск нецелевого использования ресурсов."
        )
    else:
        status = IncidentStatus.OK
        explanation = (
            f"Вся обязательная техника для этапа «{rules.stage_name}» обнаружена. "
            "План-факт соответствует нормативному составу, признаков задержки по технике нет."
        )

    # --- Financial penalty and schedule delay calculation ---
    if is_completed:
        delay_days = 0
        penalty_rub = 0
    elif status == IncidentStatus.CRITICAL:
        delay_days = max(1, int(len(missing) * 2))
        penalty_rub = delay_days * 350000
    elif status == IncidentStatus.WARNING:
        delay_days = 1
        penalty_rub = 50000
    else:
        delay_days = 0
        penalty_rub = 0

    logger.info(
        "Compliance result: stage=%r  status=%s  quality=%s  missing=%s  unexpected=%s  delay=%dd  penalty=%d rub",
        rules.stage_name,
        status.value,
        observation_quality.value,
        missing,
        unexpected,
        delay_days,
        penalty_rub,
    )

    return AnalyzeResponse(
        timestamp=datetime.now(timezone.utc),
        active_stage=rules.stage_name,
        detections=[],  # filled by caller from detector output
        status=status,
        compliance_status=status,
        explanation=explanation,
        missing_machinery=missing,
        unexpected_machinery=unexpected,
        observation_quality=observation_quality,
        camera_recommendation=camera_recommendation,
        model_is_construction_specific=model_is_construction,
        delay_days=delay_days,
        penalty_rub=penalty_rub,
        is_stage_completed=is_completed,
        stage_id=stage_id,
    )


def evaluate_batch_compliance(
    stage_name: str,
    all_detected_classes: list[str],
    total_images: int,
    *,
    model_is_real: bool = True,
    model_is_construction: bool = True,
) -> tuple[IncidentStatus, str, ObservationQuality, list[str], list[str], dict[str, int]]:
    """Compare aggregated machinery detections from multiple photos against active stage requirements.

    Addresses the partial observability problem: summing observations across
    multiple camera angles gives a complete site picture.

    Returns
    -------
    tuple of (status, explanation, observation_quality, missing, unexpected, counts_summary)
    """
    rules = get_stage_rules(stage_name)
    normalized: list[MachineryType] = []
    for class_name in all_detected_classes:
        try:
            normalized.append(MachineryType(class_name.casefold().strip()))
        except ValueError:
            continue

    counts = Counter(normalized)
    counts_summary = {k.value: v for k, v in sorted(counts.items(), key=lambda item: item[0].value)}

    missing = [
        machinery.value
        for machinery, required_count in rules.required_machinery.items()
        if counts[machinery] < required_count
    ]
    unexpected = [
        machinery.value
        for machinery in sorted(set(normalized), key=lambda m: m.value)
        if machinery not in rules.required_machinery
        and machinery not in rules.optional_machinery
    ]

    # Observation quality across multiple perspectives:
    if not model_is_real:
        quality = ObservationQuality.LOW
    elif total_images >= 2 and len(normalized) > 0:
        quality = ObservationQuality.HIGH
    elif missing and not model_is_construction:
        quality = ObservationQuality.MEDIUM
    elif normalized:
        quality = ObservationQuality.HIGH
    else:
        quality = ObservationQuality.MEDIUM

    observed_str = (
        ", ".join(f"{k}: {v}" for k, v in counts_summary.items())
        if counts_summary
        else "техника не обнаружена"
    )

    if not model_is_real:
        status = IncidentStatus.WARNING
        explanation = (
            f"Модель детекции не загружена. Агрегированный анализ {total_images} снимков "
            f"для этапа «{rules.stage_name}» выполнен в тестовом режиме."
        )
    elif not rules.required_machinery:
        status = IncidentStatus.WARNING
        explanation = (
            f"Этап «{rules.stage_name}» не найден в нормативном справочнике. "
            "Автоматическое подтверждение соответствия невозможно; добавьте правило этапа."
        )
    elif missing and model_is_construction:
        status = IncidentStatus.CRITICAL
        explanation = (
            f"Комплексный мониторинг по {total_images} снимкам выявил дефицит техники "
            f"для этапа «{rules.stage_name}». Не обнаружено: {', '.join(missing)}. "
            f"Фактически зафиксировано: {observed_str}."
        )
    elif missing and not model_is_construction:
        status = IncidentStatus.WARNING
        explanation = (
            f"По результатам анализа {total_images} снимков для этапа «{rules.stage_name}» "
            f"нормативная техника ({', '.join(missing)}) зафиксирована не полностью. "
            f"Обнаружено: {observed_str}. Используется базовая модель (COCO); "
            "рекомендуется визуальная верификация."
        )
    elif unexpected:
        status = IncidentStatus.WARNING
        explanation = (
            f"По {total_images} снимкам вся нормативная техника для этапа «{rules.stage_name}» "
            f"присутствует ({observed_str}), но зафиксирована нетипичная техника: {', '.join(unexpected)}."
        )
    else:
        status = IncidentStatus.OK
        explanation = (
            f"Комплексный мониторинг по {total_images} снимкам подтверждает 100% соответствие "
            f"плану для этапа «{rules.stage_name}». Зафиксировано: {observed_str}."
        )

    logger.info(
        "Batch compliance: stage=%r  status=%s  quality=%s  images=%d  observed=%s",
        rules.stage_name,
        status.value,
        quality.value,
        total_images,
        observed_str,
    )

    return status, explanation, quality, missing, unexpected, counts_summary