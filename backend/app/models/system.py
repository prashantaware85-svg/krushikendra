"""System metadata table (migration probe / version row)."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemInfo(Base):
    """Single-row table proving migrations have run (id=1, version=app version)."""

    __tablename__ = "system_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
