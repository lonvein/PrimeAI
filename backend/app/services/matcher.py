"""Explainable plan-versus-fact machinery compliance matching."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from ..schemas.contracts import AnalyzeResponse, IncidentStatus, MachineryType
from .ontology import get_stage_rules


def evaluate_compliance(stage_name: str, detected_classes: list[str]) -> AnalyzeResponse:
    """Compare detected machinery counts with the active stage requirements."""

    rules = get_stage_rules(stage_name)
    normalized_detected: list[MachineryType] = []
    for class_name in detected_classes:
        try:
            normalized_detected.append(MachineryType(class_name.casefold().strip()))
        except ValueError:
            continue

    counts = Counter(normalized_detected)
    missing = [
        machinery.value
        for machinery, required_count in rules.required_machinery.items()
        if counts[machinery] < required_count
    ]
    unexpected = [
        machinery.value
        for machinery in sorted(set(normalized_detected), key=lambda item: item.value)
        if machinery not in rules.required_machinery
        and machinery not in rules.optional_machinery
    ]

    if missing:
        status = IncidentStatus.CRITICAL
        explanation = (
            f"На этапе «{rules.stage_name}» не хватает обязательной техники: "
            f"{', '.join(missing)}. Это критичное отклонение плана-факта: "
            "дефицит техники может остановить текущие работы и привести к срыву сроков."
        )
    elif unexpected:
        status = IncidentStatus.WARNING
        explanation = (
            f"Обязательная техника для этапа «{rules.stage_name}» обнаружена, "
            f"но присутствует нетипичная техника: {', '.join(unexpected)}. "
            "Проверьте расстановку техники и риск нецелевого использования ресурсов."
        )
    elif not rules.required_machinery:
        status = IncidentStatus.WARNING
        explanation = (
            f"Этап «{rules.stage_name}» не найден в нормативном справочнике. "
            "Автоматическое подтверждение соответствия невозможно; добавьте правило этапа."
        )
    else:
        status = IncidentStatus.OK
        explanation = (
            f"Вся обязательная техника для этапа «{rules.stage_name}» обнаружена. "
            "План-факт соответствует нормативному составу, признаков задержки по технике нет."
        )

    return AnalyzeResponse(
        timestamp=datetime.now(timezone.utc),
        active_stage=rules.stage_name,
        detections=[],
        status=status,
        explanation=explanation,
        missing_machinery=missing,
        unexpected_machinery=unexpected,
    )