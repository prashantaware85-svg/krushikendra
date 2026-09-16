"""Crop ORM models: global variety catalogue + farmer plantings.

Contracts: ``docs/crops.md``, ``backend/README.md`` (crops endpoints),
``apps/web/lib/api.ts`` (``Crop`` / ``CropVariety`` shapes).

``FarmCrop`` carries NO ``owner`` column by design — ownership resolves
exclusively through the ``farm_id → farms`` JOIN in the repository layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CropVariety(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-style reference catalogue row (global, not farmer-scoped)."""

    __tablename__ = "crop_varieties"

    crop_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    variety_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    crop_category: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    season: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FarmCrop(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A crop planting on a farm. Soft-deleted via ``is_active`` + ``deleted_at``."""

    __tablename__ = "farm_crops"

    farm_id: Mapped[object] = mapped_column(
        Uuid,
        ForeignKey("farms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    crop_variety_id: Mapped[Optional[object]] = mapped_column(
        Uuid,
        ForeignKey("crop_varieties.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        default=None,
    )

    crop_name: Mapped[str] = mapped_column(String(64), nullable=False)
    variety_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)

    sowing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, default=None)
    expected_harvest_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, default=None)

    area_acres: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    area_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="acre")

    season: Mapped[str] = mapped_column(String(16), nullable=False, default="kharif")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sown", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def variety_id(self) -> Optional[object]:
        """Alias for ``crop_variety_id`` (short contract name)."""
        return self.crop_variety_id

    @variety_id.setter
    def variety_id(self, value: Optional[object]) -> None:
        self.crop_variety_id = value
