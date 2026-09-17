"""
База знаний предметной области. Хранит нормативы без смешивания с 
кодом нейросетей"""

# Необходимо для поддержки аннотаций типов в Python 3.7 и выше. А также 
# для предотвращения ошибки типа опережающих ссылок
from __future__ import annotations

import re

from ..schemas.contracts import MachineryType, StageRequirement


STAGE_RULES: dict[str, StageRequirement] = {
    "Подготовка территории / Демонтаж": StageRequirement(
        stage_name="Подготовка территории / Демонтаж",
        required_machinery={MachineryType.EXCAVATOR: 1, MachineryType.DUMP_TRUCK: 1},
    ),
    "Земляные работы / Котлован": StageRequirement(
        stage_name="Земляные работы / Котлован",
        required_machinery={
            MachineryType.EXCAVATOR: 1,
            MachineryType.DUMP_TRUCK: 1,
            MachineryType.BULLDOZER: 1,
        },
    ),
    "Устройство фундамента / Сваи": StageRequirement(
        stage_name="Устройство фундамента / Сваи",
        required_machinery={
            MachineryType.MOBILE_CRANE: 1,
            MachineryType.CONCRETE_MIXER: 1,
            MachineryType.TRUCK: 1,
        },
    ),
    "Монолитные работы надземной части": StageRequirement(
        stage_name="Монолитные работы надземной части",
        required_machinery={
            MachineryType.MOBILE_CRANE: 1,
            MachineryType.CONCRETE_MIXER: 1,
            MachineryType.TRUCK: 1,
        },
    ),
    "Благоустройство и дорожные работы": StageRequirement(
        stage_name="Благоустройство и дорожные работы",
        required_machinery={
            MachineryType.ROLLER: 1,
            MachineryType.DUMP_TRUCK: 1,
            MachineryType.CRANE_MANIPULATOR: 1,
        },
    ),
}

_STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Подготовка территории / Демонтаж": ("подготов", "демонтаж", "территор"),
    "Земляные работы / Котлован": ("землян", "котлован", "выем"),
    "Устройство фундамента / Сваи": ("фундамент", "сва", "основан"),
    "Монолитные работы надземной части": ("монолит", "надзем", "бетон"),
    "Благоустройство и дорожные работы": ("благоустрой", "дорож", "асфальт"),
}


def _normalize(value: str) -> str:
    """Normalize punctuation and case for predictable keyword matching."""

    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip()


def get_stage_rules(stage_name: str) -> StageRequirement:
    """Resolve a stage by exact name or Russian keywords.

    Unknown stages are represented explicitly with no requirements so the API can
    return a warning instead of silently applying an unrelated rule set.
    """

    normalized = _normalize(stage_name)
    for known_name, requirement in STAGE_RULES.items():
        if _normalize(known_name) == normalized:
            return requirement

    best_name = max(
        _STAGE_KEYWORDS,
        key=lambda name: sum(keyword in normalized for keyword in _STAGE_KEYWORDS[name]),
    )
    best_score = sum(keyword in normalized for keyword in _STAGE_KEYWORDS[best_name])
    if best_score:
        return STAGE_RULES[best_name]

    return StageRequirement(stage_name=stage_name.strip() or "Неизвестный этап")