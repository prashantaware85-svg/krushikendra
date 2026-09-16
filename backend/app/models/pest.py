"""Pest & disease tracking models (Step 12).

TRACKING ONLY — no diagnosis, prescriptions, dosages, spray advice, or
severity→treatment rules anywhere. Linking a catalogue row records "farmer
picked this label", never a confirmed diagnosis.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Pest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pest catalogue entry. Seed rows are UNVERIFIED dev samples."""

    __tablename__ = "pests"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    local_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scientific_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Disease(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Disease catalogue entry — same shape/rules as pests."""

    __tablename__ = "diseases"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    local_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scientific_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CropHealthObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One field observation (farmer-observed facts, stored verbatim)."""

    __tablename__ = "crop_health_observations"

    # NOTE: plain UUIDs — farms/crops/users live outside this rebuild;
    # scoping enforced in the service layer (uniform 404s, no IDOR oracle).
    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    farm_crop_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # pest | disease | unknown | other. `unknown` carries NO catalogue links.
    observation_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )
    pest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pests.id", ondelete="SET NULL"), nullable=True
    )
    disease_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("diseases.id", ondelete="SET NULL"), nullable=True
    )
    observed_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    observed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Display only — never a treatment trigger (no severity branches by design).
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    affected_area: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    affected_area_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)

    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # observed | monitoring | resolved | recurring
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="observed")
    # farmer | image_analysis | expert | other
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="farmer")

    # JSON array of opaque photo references (Step 10 storage class, own root).
    photo_references: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pointer only (never merged) to a live, farmer-owned analysis.
    linked_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class HealthAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One RECORDED action ("what was done") — never system output."""

    __tablename__ = "health_actions"

    observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_health_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # monitoring|sanitation|pruning|removal|irrigation_adjustment|
    # fertilizer_adjustment|biological_control|chemical_application|other
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional USER-ENTERED facts (a recorded chemical_application with a
    # product name is a farmer report — no dosage is generated/validated).
    product_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    acted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
