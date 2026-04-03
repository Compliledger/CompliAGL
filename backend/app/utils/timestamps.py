"""Timestamp utility helpers."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()
