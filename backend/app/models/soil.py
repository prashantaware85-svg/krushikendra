"""Soil test + fertilizer usage models (Step 11).

RECORDS ONLY — no dosage recommendations, prescriptions, mixing
instructions, or agronomic advice anywhere in this step. Values are stored
EXACTLY as reported (never converted); NULL means "not measured", never 0.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SoilTest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One lab soil-test record for a farm (many per farm, newest-first)."""

    __tablename__ = "soil_tests"

    # NOTE: plain UUIDs (no hard FKs) — farms/users live outside this
    # rebuild; scoping enforced in the service layer (uniform 404s).
    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    tested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    lab_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    laboratory_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    report_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Nutrients as NUMERIC (never float): pH 0–14 unitless; EC dS/m;
    # organic carbon %; N/P/K/S kg/ha; Zn/Fe/Mn/Cu/B mg/kg.
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    electrical_conductivity: Mapped[float | None] = mapped_column(
        Numeric(6, 3), nullable=True
    )
    organic_carbon: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    phosphorus: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    potassium: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    sulphur: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    zinc: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    iron: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    manganese: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    copper: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    boron: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Opaque storage reference (never a path); responses carry has_report only.
    report_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FertilizerApplication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One fertilizer USAGE record ("farmer used X") — never a recommendation."""

    __tablename__ = "fertilizer_applications"

    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    farm_crop_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    fertilizer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fertilizer_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity_kg: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    quantity_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    application_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(256), nullable=True)
    applied_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
