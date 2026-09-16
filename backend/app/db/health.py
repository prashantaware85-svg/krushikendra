"""Database connectivity probe (used by /api/v1/health/db + tests).

Security: failures NEVER surface connection details (host, user, password).
Only the exception type is logged server-side; clients get a generic 503.
"""

from __future__ import annotations

import logging

from fastapi import status
from sqlalchemy import Engine, text

from app.core.errors import AppError
from app.db.session import get_engine

logger = logging.getLogger("krushi-seva.db")


class DatabaseUnavailableError(AppError):
    """Raised when no DB connection can be established (→ HTTP 503)."""

    def __init__(self) -> None:
        super().__init__(
            "Database is currently unavailable. Please try again later.",
            code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def check_database(engine: Engine | None = None) -> None:
    """Open and close one connection. Raises DatabaseUnavailableError."""
    eng = engine or get_engine()
    try:
        with eng.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — any driver/network failure → 503
        # Log ONLY the error type: never host/user/password/DSN fragments.
        logger.warning("Database health check failed: %s", type(exc).__name__)
        raise DatabaseUnavailableError from exc
