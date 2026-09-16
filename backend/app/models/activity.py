"""Crop-activity ORM model (manual records only — no advisory logic).

Contracts: ``docs/crop-activities.md``, ``backend/README.md``
(activities + timeline endpoints), ``apps/web/lib/api.ts`` (``Activity``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FarmActivity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A farmer-recorded activity on a planting. Soft-deleted on DELETE."""

    __tablename__ = "farm_activities"

    farm_crop_id: Mapped[object] = mapped_column(
        Uuid,
        ForeignKey("farm_crops.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")

    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    cost_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def cost(self) -> Optional[float]:
        """Alias for ``cost_amount`` (frontend contract name)."""
        return self.cost_amount

    @cost.setter
    def cost(self, value: Optional[float]) -> None:
        self.cost_amount = value
