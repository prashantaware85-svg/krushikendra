"""Weather cache ORM model (measured data snapshots only).

Contracts: ``docs/weather.md``, ``backend/README.md`` (weather endpoints).

``weather_records`` is a DB-backed cache (no Redis in this project):
one row per (rounded coordinates, kind). Refreshes UPDATE rows in place —
no history buildup. Facts only: no advisory, alerts, or predictions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeatherRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cached weather snapshot / forecast payload for rounded coordinates."""

    __tablename__ = "weather_records"

    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="current")
    recorded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    rainfall_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
