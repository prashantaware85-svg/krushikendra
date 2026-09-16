"""Database connectivity endpoint.

GET /api/v1/health/db
  reachable   → 200 {"status": "ok", "database": "connected"}
  unreachable → 503 {"error": {"code": "DATABASE_UNAVAILABLE", ...}}
                  (AppError handler; never leaks credentials/DSN details)
"""

from fastapi import APIRouter

from app.db.health import check_database

router = APIRouter(tags=["health"])


@router.get("/health/db", summary="Database connectivity check")
def database_health() -> dict:
    """Probe the database with a single SELECT 1 (no ORM/tables needed)."""
    check_database()
    return {"status": "ok", "database": "connected"}
