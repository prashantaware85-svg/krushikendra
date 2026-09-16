"""Application factory + process-level wiring.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

logger = logging.getLogger("krushi-seva")


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS must be registered before routers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["health"], summary="Infrastructure health check")
    def root_health() -> dict:
        """Dependency-free liveness probe for orchestrators/LBs."""
        return {
            "status": "ok",
            "service": "krushi-seva-backend",
            "version": settings.version,
            "environment": settings.environment,
        }

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    logger.info(
        "Krushi Seva backend initialised (env=%s, version=%s)",
        settings.environment,
        settings.version,
    )
    return app


app = create_app()
