"""Alembic environment: live URL from Settings, metadata from app.db.base.Base."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import _normalize_db_url

# Ensure all models are registered on Base.metadata for autogenerate/diffs.
import app.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# The live URL ALWAYS comes from the environment via Settings — never from
# alembic.ini (that file holds a local placeholder only). Normalize exactly
# like app.db.session: Render's bare ``postgresql://`` resolves to SQLAlchemy's
# default psycopg2 dialect, which is NOT installed (psycopg v3 only). SQLite
# URLs pass through untouched.
db_url = _normalize_db_url(settings.database_url)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
