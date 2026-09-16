"""UTC time helpers.

PostgreSQL returns timestamptz as timezone-aware datetimes, but SQLite
(testing) returns naive ones. All comparisons go through `coerce_utc()` so
auth expiry logic behaves identically on both.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time, timezone-aware."""
    return datetime.now(timezone.utc)


def coerce_utc(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite reads) as UTC; pass aware ones through."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
