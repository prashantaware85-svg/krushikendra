"""SQLAlchemy engine + session management (sync, psycopg).

Lifetime rules:
- One process-wide `Engine` (lazy singleton) with a bounded `QueuePool`.
- One short-lived `Session` per request via the `get_db` FastAPI dependency,
  always closed in `finally` — connections are never leaked.
- SQLite URLs are supported ONLY for tests/local tooling; production is
  PostgreSQL. Pool options are Postgres-only (SQLite uses StaticPool).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def build_engine(settings: Settings | None = None) -> Engine:
    """Create a NEW engine from settings (no caching — used by get_engine)."""
    settings = settings or get_settings()
    url = settings.database_url

    if _is_sqlite(url):
        # Tests/tooling only: single shared in-memory-friendly connection.
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # PostgreSQL (psycopg, sync): bounded pool + fail-fast connect timeout.
    return create_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,  # recycle stale connections instead of failing requests
        connect_args={"connect_timeout": settings.database_connect_timeout},
    )


def get_engine(settings: Settings | None = None) -> Engine:
    """Process-wide engine singleton (lazy). Pass settings only to override."""
    global _engine
    if _engine is None or settings is not None:
        if settings is not None:
            dispose_engine()
        _engine = build_engine(settings)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Session factory bound to the singleton engine (lazy)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), class_=Session, expire_on_commit=False
        )
    return _session_factory


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, ALWAYS closes it afterwards.

    Usage:
        @router.get("/farmers")
        def list_farmers(db: Session = Depends(get_db)): ...
    """
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def dispose_engine() -> None:
    """Dispose the singleton engine + factory (tests, shutdown hooks)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = cast("sessionmaker[Session] | None", None)
