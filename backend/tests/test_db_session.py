"""Unit test for Render postgresql:// URL normalization (psycopg v3).

Smallest safe check: postgresql:// → postgresql+psycopg:// before create_engine,
preserving already-qualified URLs and SQLite test URLs.
"""

from app.core.config import Settings
from app.db.session import _normalize_db_url, build_engine


def test_normalize_bare_postgres():
    assert _normalize_db_url("postgresql://user:pw@host/db") == "postgresql+psycopg://user:pw@host/db"
    assert _normalize_db_url("postgresql://localhost/krushi_seva") == "postgresql+psycopg://localhost/krushi_seva"


def test_normalize_already_qualified_unchanged():
    url = "postgresql+psycopg://user:pw@host/db"
    assert _normalize_db_url(url) == url


def test_normalize_sqlite_unchanged():
    assert _normalize_db_url("sqlite://") == "sqlite://"
    assert _normalize_db_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert _normalize_db_url("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"


def test_build_engine_normalizes_postgresql(monkeypatch):
    # Use Settings with bare postgresql:// and verify engine URL is normalized.
    # No DB connection is attempted until first use; engine creation is safe.
    s = Settings(database_url="postgresql://postgres:pw@localhost:5432/krushi_seva")
    engine = build_engine(s)
    # SQLAlchemy URL object string should contain +psycopg
    assert "+psycopg" in str(engine.url)
    assert str(engine.url).startswith("postgresql+psycopg://")
    engine.dispose()


def test_build_engine_preserves_qualified():
    s = Settings(database_url="postgresql+psycopg://postgres:pw@localhost:5432/krushi_seva")
    engine = build_engine(s)
    assert str(engine.url).startswith("postgresql+psycopg://")
    engine.dispose()


def test_build_engine_sqlite_still_staticpool():
    s = Settings(database_url="sqlite://")
    engine = build_engine(s)
    # StaticPool is used for sqlite, not QueuePool
    from sqlalchemy.pool import StaticPool

    assert isinstance(engine.pool, StaticPool)
    engine.dispose()
