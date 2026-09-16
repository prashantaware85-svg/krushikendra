"""Farm + soil-record ORM models.

Contracts: ``docs/farms.md``, ``backend/README.md`` (farms endpoints),
``apps/web/lib/api.ts`` (``Farm`` / ``Soil`` snake_case shapes).

Ownership: ``owner_user_id`` is a logical FK to the auth ``users`` identity
(auth module owns that table, so no DB-level FK constraint here — this keeps
SQLite/PG parity and lets auth be restored independently).
Farmer scoping (``owner_user_id == current_user.id`` + live rows only) is
enforced in ``app/modules/farms/repository.py``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Farm(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A farmer's farm. Soft-deleted via ``is_active`` + ``deleted_at``."""

    __tablename__ = "farms"

    owner_user_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    farm_name: Mapped[str] = mapped_column(String(128), nullable=False)

    village: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    taluka: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)

    area_acres: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    area_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="acre")

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)

    land_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    soil_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    irrigation_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    water_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    ownership_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def name(self) -> str:
        """Alias for ``farm_name`` (short contract name)."""
        return self.farm_name

    @name.setter
    def name(self, value: str) -> None:
        self.farm_name = value


class SoilRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One soil record per farm (singleton enforced by unique ``farm_id``)."""

    __tablename__ = "soil_records"

    farm_id: Mapped[object] = mapped_column(
        Uuid,
        ForeignKey("farms.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    soil_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    soil_test_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    soil_test_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, default=None)

    ph: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    organic_carbon: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    nitrogen: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    phosphorus: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    potassium: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)

    soil_test_document_reference: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, default=None
    )

    @property
    def tested_on(self) -> Optional[date]:
        """Alias for ``soil_test_date`` (short contract name)."""
        return self.soil_test_date

    @tested_on.setter
    def tested_on(self, value: Optional[date]) -> None:
        self.soil_test_date = value
