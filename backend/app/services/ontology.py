"""Domain knowledge base: normative machinery requirements per construction stage.

Two rule sources (layered, schedule takes priority):
1. STAGE_RULES — hardcoded fallback rules for 5 common construction phases.
2. Schedule-derived rules — loaded dynamically when Excel schedule is uploaded.
   These contain exact names and counts from the official ДГП template.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import TYPE_CHECKING

from ..schemas.contracts import MachineryType, StageRequirement

if TYPE_CHECKING:
    from .schedule_parser import ScheduleRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static fallback rules (used when no schedule is uploaded).
# ---------------------------------------------------------------------------
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
    "Подготовка территории / Демонтаж": ("подготов", "демонтаж", "территор", "снос", "расчист"),
    "Земляные работы / Котлован": ("землян", "котлован", "выем", "грунт", "разработк"),
    "Устройство фундамента / Сваи": ("фундамент", "сва", "основан", "буронабив"),
    "Монолитные работы надземной части": ("монолит", "надзем", "бетон", "возведен"),
    "Благоустройство и дорожные работы": ("благоустрой", "дорож", "асфальт", "проезд"),
}

# ---------------------------------------------------------------------------
# Dynamic schedule-derived rules (thread-safe).
# ---------------------------------------------------------------------------
_schedule_lock = threading.Lock()
_schedule_rules: dict[str, StageRequirement] = {}
_schedule_keywords: dict[str, tuple[str, ...]] = {}


def load_schedule_rules(rows: list[ScheduleRow]) -> int:
    """Replace dynamic rules from a parsed schedule.

    Returns the number of stages loaded. Thread-safe.
    """
    from .schedule_parser import schedule_row_to_stage_requirement  # noqa: PLC0415

    new_rules: dict[str, StageRequirement] = {}
    new_keywords: dict[str, tuple[str, ...]] = {}

    for row in rows:
        req = schedule_row_to_stage_requirement(row)
        if req.required_machinery:
            new_rules[req.stage_name] = req
            # Generate keywords from stage name words (3+ chars).
            words = _normalize(req.stage_name).split()
            kws = tuple(w for w in words if len(w) >= 3)
            new_keywords[req.stage_name] = kws

    with _schedule_lock:
        _schedule_rules.clear()
        _schedule_rules.update(new_rules)
        _schedule_keywords.clear()
        _schedule_keywords.update(new_keywords)

    logger.info("Loaded %d schedule-derived stage rules.", len(new_rules))
    return len(new_rules)


def get_all_stage_names() -> list[str]:
    """Return combined list of all known stage names (schedule + static)."""
    with _schedule_lock:
        names = list(_schedule_rules.keys())
    # Add static rules that are not overridden by schedule.
    for name in STAGE_RULES:
        if name not in names:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(value: str) -> str:
    """Normalize punctuation and case for predictable keyword matching."""
    return re.sub(r"\s+", " ", value.casefold().replace("ё", "е")).strip()


def _keyword_score(stage_keywords: dict[str, tuple[str, ...]], normalized: str) -> tuple[str, int]:
    """Return the best-matching stage name and its score."""
    best_name = ""
    best_score = 0
    for name, keywords in stage_keywords.items():
        score = sum(1 for kw in keywords if kw in normalized)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name, best_score


# ---------------------------------------------------------------------------
# Main lookup function.
# ---------------------------------------------------------------------------

def get_stage_rules(stage_name: str) -> StageRequirement:
    """Resolve a stage by exact name or Russian keywords.

    Lookup order:
    1. Exact match in schedule-derived rules.
    2. Keyword match in schedule-derived rules.
    3. Exact match in static fallback rules.
    4. Keyword match in static fallback rules.
    5. Return empty StageRequirement (unknown stage).
    """
    normalized = _normalize(stage_name)

    # --- Schedule-derived rules (take priority) ---
    with _schedule_lock:
        sched_rules = dict(_schedule_rules)
        sched_kw = dict(_schedule_keywords)

    for known_name, requirement in sched_rules.items():
        if _normalize(known_name) == normalized:
            return requirement

    if sched_kw:
        best_name, best_score = _keyword_score(sched_kw, normalized)
        if best_score > 0:
            return sched_rules[best_name]

    # --- Static fallback rules ---
    for known_name, requirement in STAGE_RULES.items():
        if _normalize(known_name) == normalized:
            return requirement

    best_name, best_score = _keyword_score(_STAGE_KEYWORDS, normalized)
    if best_score > 0:
        return STAGE_RULES[best_name]

    return StageRequirement(stage_name=stage_name.strip() or "Неизвестный этап")