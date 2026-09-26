"""Alembic database URL handling (psycopg v3 consistency).

Regression guard for the Render deployment failure: alembic/env.py must
normalize the live URL exactly like app.db.session, because a bare
``postgresql://`` scheme resolves to SQLAlchemy's default psycopg2 dialect,
which is NOT installed (psycopg v3 only). Subprocess ``alembic`` runs prove
the migration chain works end-to-end: offline SQL generation with the Render
URL, and a full online upgrade against SQLite (pass-through URL).
"""

import configparser
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import _normalize_db_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_ini_placeholder_uses_psycopg3():
    parser = configparser.ConfigParser()
    parser.read(str(BACKEND_DIR / "alembic.ini"))
    url = parser.get("alembic", "sqlalchemy.url")
    assert url.startswith("postgresql+psycopg://")
    assert "psycopg2" not in url


def test_env_py_resolution_matches_app_normalization():
    s = Settings(database_url="postgresql://postgres:pw@localhost:5432/krushi_seva")
    normalized = _normalize_db_url(s.database_url)
    assert make_url(normalized).drivername == "postgresql+psycopg"


def test_bare_postgresql_scheme_defaults_to_psycopg2():
    # Root cause: unqualified postgresql:// has no +driver, so SQLAlchemy
    # falls back to its default psycopg2 dialect (not installed here).
    assert make_url("postgresql://user:pw@host/db").drivername == "postgresql"


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["ENVIRONMENT"] = "test"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_DIR),
        env=env,
        check=False,
    )


def test_alembic_offline_bare_postgresql_needs_no_psycopg2():
    # Render failure URL end-to-end: must emit SQL without importing psycopg2.
    result = _run_alembic(
        "postgresql://postgres:pw@localhost:5432/krushi_seva", "upgrade", "head", "--sql"
    )
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "psycopg2" not in result.stderr
    assert result.stdout.strip()


def test_alembic_online_sqlite_upgrade_head(tmp_path):
    # Full online migration chain (env.py online path, real connection):
    # SQLite URLs pass through normalization untouched.
    db_file = (tmp_path / "alembic_test.db").as_posix()
    result = _run_alembic(f"sqlite:///{db_file}", "upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
