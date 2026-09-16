"""Liveness probe for the versioned API (dependency-free by design)."""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="API v1 health check")
def health_check() -> dict:
    """Return service liveness. No DB/auth — safe for load-balancers."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "krushi-seva-backend",
        "version": settings.version,
        "environment": settings.environment,
    }
