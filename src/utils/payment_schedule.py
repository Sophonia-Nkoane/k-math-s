from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, List, Optional


def normalize_due_days(raw_days: Any = None, fallback_day: Any = None) -> List[int]:
    candidates: List[Any] = []

    if isinstance(raw_days, str):
        text = raw_days.strip()
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = [part.strip() for part in text.split(",")]
            raw_days = parsed
        else:
            raw_days = []

    if raw_days is None:
        raw_items: List[Any] = []
    elif isinstance(raw_days, (list, tuple, set)):
        raw_items = list(raw_days)
    else:
        raw_items = [raw_days]

    for item in raw_items:
        if isinstance(item, str) and "," in item and not item.strip().startswith("["):
            candidates.extend(part.strip() for part in item.split(","))
        else:
            candidates.append(item)

    normalized: List[int] = []
    for item in candidates:
        if item in (None, ""):
            continue
        try:
            day = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if 1 <= day <= 31 and day not in normalized:
            normalized.append(day)

    normalized.sort()

    if normalized:
        return normalized

    try:
        fallback = int(fallback_day)
    except (TypeError, ValueError):
        fallback = 1

    fallback = max(1, min(31, fallback))
    return [fallback]


def primary_due_day(raw_days: Any = None, fallback_day: Any = None) -> int:
    return normalize_due_days(raw_days=raw_days, fallback_day=fallback_day)[0]


def serialize_due_days(raw_days: Any = None, fallback_day: Any = None) -> str:
    return json.dumps(
        normalize_due_days(raw_days=raw_days, fallback_day=fallback_day),
        separators=(",", ":"),
    )


def format_due_days(raw_days: Any = None, fallback_day: Any = None) -> str:
    return ", ".join(str(day) for day in normalize_due_days(raw_days=raw_days, fallback_day=fallback_day))


def _coerce_schedule_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text.replace("T", " ")).date()
    except ValueError:
        return None


def normalize_scheduled_dates(raw_dates: Any = None) -> List[str]:
    if isinstance(raw_dates, str):
        text = raw_dates.strip()
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = [part.strip() for part in text.split(",")]
            raw_dates = parsed
        else:
            raw_dates = []

    if raw_dates is None:
        raw_items: List[Any] = []
    elif isinstance(raw_dates, (list, tuple, set)):
        raw_items = list(raw_dates)
    else:
        raw_items = [raw_dates]

    normalized: List[str] = []
    for item in raw_items:
        parsed_date = _coerce_schedule_date(item)
        if not parsed_date:
            continue
        iso_value = parsed_date.isoformat()
        if iso_value not in normalized:
            normalized.append(iso_value)

    normalized.sort()
    return normalized


def serialize_scheduled_dates(raw_dates: Any = None) -> Optional[str]:
    normalized = normalize_scheduled_dates(raw_dates=raw_dates)
    if not normalized:
        return None
    return json.dumps(normalized, separators=(",", ":"))


def format_scheduled_dates(raw_dates: Any = None) -> str:
    return ", ".join(normalize_scheduled_dates(raw_dates=raw_dates))


def next_scheduled_date(raw_dates: Any = None, reference_date: Any = None) -> Optional[date]:
    normalized = normalize_scheduled_dates(raw_dates=raw_dates)
    if not normalized:
        return None

    reference = _coerce_schedule_date(reference_date) or date.today()
    parsed_dates = [_coerce_schedule_date(item) for item in normalized]
    valid_dates = [item for item in parsed_dates if item is not None]
    if not valid_dates:
        return None

    for schedule_date in valid_dates:
        if schedule_date >= reference:
            return schedule_date
    return valid_dates[-1]
