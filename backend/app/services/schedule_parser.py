"""Schedule parser: reads the ДГП Excel schedule and extracts structured stage requirements.

Key responsibilities:
1. Parse raw Excel rows into ScheduleRow objects with typed dates.
2. Parse the "Нормативная техника (План)" text column into {MachineryType: count} dicts.
3. Find which stage(s) are active on a given date.
4. Build StageRequirement objects for use by the matcher/ontology.

Russian machinery name mapping (from Excel → MachineryType):
    Экскаватор      → excavator
    Самосвал        → dump_truck
    Бульдозер       → bulldozer
    Автобетоносмеситель / Бетоносмеситель → concrete_mixer
    Автокран / Кран → mobile_crane
    Башенный кран   → mobile_crane (no separate class yet)
    Кран-манипулятор→ crane_manipulator
    Каток           → roller
    Грузовик        → truck
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import threading
from typing import Any

import pandas as pd

from ..schemas.contracts import MachineryType, ScheduleRow, StageRequirement

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Russian term → MachineryType mapping.
# Keys are lowercased stems (checked with str.startswith for flexibility).
# ---------------------------------------------------------------------------
_RUSSIAN_TO_TYPE: list[tuple[str, MachineryType]] = [
    ("экскаватор",            MachineryType.EXCAVATOR),
    ("самосвал",              MachineryType.DUMP_TRUCK),
    ("бульдозер",             MachineryType.BULLDOZER),
    ("автобетоносмеситель",   MachineryType.CONCRETE_MIXER),
    ("бетоносмеситель",       MachineryType.CONCRETE_MIXER),
    ("кран-манипулятор",      MachineryType.CRANE_MANIPULATOR),
    ("манипулятор",           MachineryType.CRANE_MANIPULATOR),
    ("башенный кран",         MachineryType.MOBILE_CRANE),
    ("автокран",              MachineryType.MOBILE_CRANE),
    ("кран",                  MachineryType.MOBILE_CRANE),
    ("каток",                 MachineryType.ROLLER),
    ("грузовик",              MachineryType.TRUCK),
]

# Regex: "Экскаватор (2)" or "Экскаватор(2)" or "Экскаватор"
_ITEM_RE = re.compile(r"([А-Яа-яёЁ\- ]+?)(?:\s*\((\d+)\))?(?:,|$)")


def parse_machinery_text(text: str) -> dict[MachineryType, int]:
    """Parse Russian machinery plan text to a {MachineryType: count} dict.

    Examples
    --------
    >>> parse_machinery_text("Экскаватор (2), Самосвал (4)")
    {MachineryType.EXCAVATOR: 2, MachineryType.DUMP_TRUCK: 4}
    >>> parse_machinery_text("Бульдозер (1), Каток (1), Грузовик (2)")
    {MachineryType.BULLDOZER: 1, MachineryType.ROLLER: 1, MachineryType.TRUCK: 2}
    """
    if not text or not isinstance(text, str):
        return {}

    result: dict[MachineryType, int] = {}
    for match in _ITEM_RE.finditer(text.strip()):
        raw_name = match.group(1).strip().lower().replace("ё", "е")
        count = int(match.group(2)) if match.group(2) else 1

        matched_type: MachineryType | None = None
        for stem, mtype in _RUSSIAN_TO_TYPE:
            if raw_name.startswith(stem) or stem in raw_name:
                matched_type = mtype
                break

        if matched_type:
            # Sum counts if same type appears multiple times.
            result[matched_type] = result.get(matched_type, 0) + count
        else:
            logger.debug("Unknown machinery name in schedule: %r", match.group(1).strip())

    return result


def _parse_date(value: Any) -> datetime | None:
    """Convert various date representations to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return None


def to_date(value: Any) -> date | None:
    """Normalize any date/datetime/string representation to datetime.date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()
    if isinstance(value, str):
        clean_val = value.strip().split("T")[0].split(" ")[0]
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(clean_val, fmt).date()
            except ValueError:
                continue
    return None


def parse_schedule(file_bytes: bytes) -> list[dict[str, Any]]:
    """Read the first Excel sheet into JSON-compatible row dictionaries.

    Returns raw dicts (for backward-compat with existing /schedule/upload endpoint).
    Timestamps are serialised to ISO strings so they survive JSON encoding.
    """
    try:
        frame = pd.read_excel(BytesIO(file_bytes))
    except Exception as exc:
        logger.error("Failed to parse Excel schedule: %s", exc)
        raise ValueError(f"Cannot read Excel file: {exc}") from exc

    # Replace NaN with None for JSON compatibility.
    frame = frame.where(pd.notna(frame), None)

    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        # Serialise Timestamps to ISO strings.
        serialised = {}
        for key, val in row.items():
            if isinstance(val, (pd.Timestamp, datetime)):
                serialised[key] = val.isoformat() if pd.notna(val) else None
            else:
                serialised[key] = val
        rows.append(serialised)
    return rows


def parse_schedule_structured(file_bytes: bytes) -> list[ScheduleRow]:
    """Parse Excel into typed ScheduleRow objects with machinery requirements.

    This is the structured version used by the Plan vs Fact pipeline.
    """
    try:
        frame = pd.read_excel(BytesIO(file_bytes))
    except Exception as exc:
        logger.error("Failed to parse Excel schedule: %s", exc)
        raise ValueError(f"Cannot read Excel file: {exc}") from exc

    frame = frame.where(pd.notna(frame), None)

    # Try to map columns flexibly (column names may vary between Excel templates).
    col_map = _detect_columns(frame.columns.tolist())
    logger.debug("Schedule column mapping: %s", col_map)

    rows: list[ScheduleRow] = []
    for idx, raw in enumerate(frame.to_dict(orient="records")):
        stage_name = _get(raw, col_map, "stage_name")
        machinery_text = _get(raw, col_map, "machinery_plan")
        if not stage_name:
            continue  # skip header-like or empty rows

        required = parse_machinery_text(machinery_text or "")

        rows.append(
            ScheduleRow(
                index=idx,
                stage_name=str(stage_name).strip(),
                zone=str(_get(raw, col_map, "zone") or "").strip() or None,
                date_start=_parse_date(_get(raw, col_map, "date_start")),
                date_end=_parse_date(_get(raw, col_map, "date_end")),
                days=_safe_int(_get(raw, col_map, "days")),
                machinery_plan=machinery_text,
                required_machinery={k.value: v for k, v in required.items()},
                contractor=str(_get(raw, col_map, "contractor") or "").strip() or None,
            )
        )
    return rows


def get_active_stages(
    schedule: list[ScheduleRow],
    query_date: datetime | date | str,
) -> list[ScheduleRow]:
    """Return all stages whose date interval contains query_date.

    Normalized to datetime.date to avoid time-of-day or type mismatch errors.
    """
    target = to_date(query_date)
    if target is None:
        return []

    active = []
    for row in schedule:
        s_start = to_date(row.date_start)
        s_end = to_date(row.date_end)
        if s_start and s_end and s_start <= target <= s_end:
            active.append(row)
    return active


def schedule_row_to_stage_requirement(row: ScheduleRow) -> StageRequirement:
    """Convert a ScheduleRow to the StageRequirement format the matcher expects."""
    return StageRequirement(
        stage_name=row.stage_name,
        required_machinery={
            MachineryType(k): v for k, v in row.required_machinery.items()
        },
    )


# ---------------------------------------------------------------------------
# Global Schedule Cache and Date-based Stage Resolution
# ---------------------------------------------------------------------------
_schedule_lock = threading.Lock()
_loaded_schedule: list[ScheduleRow] = []


def _find_default_schedule_file() -> Path | None:
    """Find default Moscow DGP schedule Excel template."""
    base_dir = Path(__file__).resolve().parents[3]
    for rel_path in [
        Path("MSC_lct/График_шаблон.xlsx"),
        Path("data/Сводный перечень строительных работ_ЛТЦ.xlsx"),
    ]:
        p1 = base_dir / rel_path
        if p1.is_file():
            return p1
        if rel_path.is_file():
            return rel_path
    return None


def ensure_default_schedule_loaded() -> list[ScheduleRow]:
    """Ensure that the default schedule template is loaded in memory."""
    global _loaded_schedule
    with _schedule_lock:
        if _loaded_schedule:
            return list(_loaded_schedule)

        schedule_path = _find_default_schedule_file()
        if schedule_path and schedule_path.is_file():
            try:
                rows = parse_schedule_structured(schedule_path.read_bytes())
                _loaded_schedule = rows
                logger.info(
                    "Auto-loaded default schedule from %s (%d stages)",
                    schedule_path,
                    len(rows),
                )
                try:
                    from .ontology import load_schedule_rules  # noqa: PLC0415
                    load_schedule_rules(rows)
                except Exception as exc:
                    logger.warning("Could not sync default schedule rules to ontology: %s", exc)
                return list(_loaded_schedule)
            except Exception as exc:
                logger.error("Failed to parse default schedule %s: %s", schedule_path, exc)
    return []


def get_loaded_schedule() -> list[ScheduleRow]:
    """Return currently loaded schedule rows, initializing from template if needed."""
    with _schedule_lock:
        if _loaded_schedule:
            return list(_loaded_schedule)
    return ensure_default_schedule_loaded()


def set_loaded_schedule(rows: list[ScheduleRow]) -> None:
    """Set the active schedule rows and update ontology stage rules."""
    global _loaded_schedule
    with _schedule_lock:
        _loaded_schedule = list(rows)
    try:
        from .ontology import load_schedule_rules  # noqa: PLC0415
        load_schedule_rules(rows)
    except Exception as exc:
        logger.warning("Could not sync schedule rules to ontology: %s", exc)


def get_schedule_date_range() -> tuple[datetime | None, datetime | None]:
    """Return (min_start_date, max_end_date) across all stages in active schedule."""
    schedule = get_loaded_schedule()
    starts = [r.date_start for r in schedule if r.date_start]
    ends = [r.date_end for r in schedule if r.date_end]
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)


def get_active_stage_by_date(target_date: datetime | date | str) -> ScheduleRow | None:
    """Find the active stage from the loaded schedule for a given date.

    If multiple stages overlap on target_date, returns the one that started
    most recently (highest date_start). All comparisons are done as datetime.date.
    """
    target = to_date(target_date)
    if target is None:
        return None

    schedule = get_loaded_schedule()
    active = get_active_stages(schedule, target)
    if not active:
        return None

    return max(active, key=lambda r: to_date(r.date_start) or date.min)


def get_nearest_stage(target_date: datetime | date | str) -> tuple[ScheduleRow, int] | None:
    """Find the chronologically closest stage to target_date when none is active.

    Returns tuple (nearest_stage, days_distance) or None if schedule is empty.
    Positive distance = target is before stage; negative = target is after stage.
    """
    target = to_date(target_date)
    if target is None:
        return None

    schedule = get_loaded_schedule()
    valid_stages = [r for r in schedule if to_date(r.date_start) and to_date(r.date_end)]
    if not valid_stages:
        return None

    def distance_to_stage(row: ScheduleRow) -> int:
        s_start = to_date(row.date_start)
        s_end = to_date(row.date_end)
        if s_start <= target <= s_end:
            return 0
        if target < s_start:
            return (s_start - target).days
        return (target - s_end).days

    nearest = min(valid_stages, key=distance_to_stage)
    dist = distance_to_stage(nearest)
    return nearest, dist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Column detection keywords (lowercased).
_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "stage_name":     ["наименование", "этап", "работ"],
    "zone":           ["зона", "участок", "сектор"],
    "date_start":     ["начала", "начало", "start"],
    "date_end":       ["окончания", "конец", "end", "финиш"],
    "days":           ["дней", "days", "длительность"],
    "machinery_plan": ["техника", "план", "machinery"],
    "contractor":     ["подрядчик", "contractor", "исполнитель"],
}


def _detect_columns(columns: list[str]) -> dict[str, str | None]:
    """Map logical field names to actual Excel column names."""
    mapping: dict[str, str | None] = {k: None for k in _COLUMN_KEYWORDS}
    for col in columns:
        col_lower = str(col).lower()
        for field, keywords in _COLUMN_KEYWORDS.items():
            if mapping[field] is None:
                if any(kw in col_lower for kw in keywords):
                    mapping[field] = col
                    break
    return mapping


def _get(row: dict[str, Any], col_map: dict[str, str | None], field: str) -> Any:
    col = col_map.get(field)
    if col is None:
        return None
    return row.get(col)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None