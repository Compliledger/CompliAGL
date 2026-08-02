"""Timestamp utility helpers."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()


def ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
    """Return *value* as a timezone-aware UTC datetime (or ``None``)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


_ISO8601_DURATION = re.compile(
    r"^P"
    r"(?:(?P<weeks>\d+)W)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def parse_iso8601_duration(value: Optional[str]) -> Optional[timedelta]:
    """Parse a restricted ISO-8601 duration (e.g. ``P30D``, ``P7D``, ``PT1H``).

    Only the day/week/hour/minute/second components are supported (months and
    years are intentionally excluded because they are not fixed-length). Returns
    ``None`` when *value* is empty or cannot be parsed.
    """
    if not value or not isinstance(value, str):
        return None
    match = _ISO8601_DURATION.match(value.strip())
    if not match or value.strip() == "P":
        return None
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    return timedelta(
        weeks=parts["weeks"],
        days=parts["days"],
        hours=parts["hours"],
        minutes=parts["minutes"],
        seconds=parts["seconds"],
    )
