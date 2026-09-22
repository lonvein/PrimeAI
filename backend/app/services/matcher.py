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
    model_is_real: bool = True,
    model_is_construction: bool = False,
) -> AnalyzeResponse:
    """Compare detected machinery counts with the active stage requirements.

    Parameters
    ----------
    stage_name:
        Name of the construction stage (matched against ontology).
    detected_classes:
        List of MachineryType value strings returned by the detector.
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

    # --- Determine observation quality ---
    if not model_is_real:
        observation_quality = ObservationQuality.LOW
    elif missing and not model_is_construction:
        # Generic COCO model cannot see most construction classes.
        # Absence in photo ≠ absence on site.
        observation_quality = ObservationQuality.MEDIUM
    elif normalized:
        observation_quality = ObservationQuality.HIGH
    else:
        observation_quality = ObservationQuality.MEDIUM

    # --- Determine status and explanation ---
    if not model_is_real:
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
        # Do NOT escalate to CRITICAL because absence of detection ≠ absence of equipment.
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

    logger.info(
        "Compliance result: stage=%r  status=%s  quality=%s  missing=%s  unexpected=%s",
        rules.stage_name,
        status.value,
        observation_quality.value,
        missing,
        unexpected,
    )

    return AnalyzeResponse(
        timestamp=datetime.now(timezone.utc),
        active_stage=rules.stage_name,
        detections=[],  # filled by caller from detector output
        status=status,
        explanation=explanation,
        missing_machinery=missing,
        unexpected_machinery=unexpected,
        observation_quality=observation_quality,
        model_is_construction_specific=model_is_construction,
    )