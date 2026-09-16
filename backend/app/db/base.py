"""Declarative base + reusable column mixins for all future models.

Conventions (Step 2 architecture decisions):
- UUID primary keys (client-generated `uuid4`) — no auto-increment integers,
  so IDs are safe to generate at the edge and merge across future services.
- UTC timestamps via server default (`func.now()` → timestamptz on Postgres).
- Naming convention for constraints so Alembic autogenerate produces
  deterministic migration diffs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base. All models MUST inherit from this."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """UUID PK for future domain entities (Step 3+ MUST use this)."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """UTC audit timestamps. Server-side default — never trust client clocks."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Re-exported for convenience; Alembic env.py imports Base.
__all__ = ["Base", "UUIDPrimaryKeyMixin", "TimestampMixin"]
