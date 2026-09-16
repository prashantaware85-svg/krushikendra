"""Crop image analysis model (Step 10).

Stores UNCERTAIN observations only — never a diagnosis, dosage, or
prescription. Frontend never sees storage paths (opaque references served
through an authed byte route).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CropImageAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One farmer photo upload + vision observation run."""

    __tablename__ = "crop_image_analyses"

    # NOTE: plain UUIDs (no hard FKs) — farms/farm_crops/users live in lost
    # domains outside this rebuild. Scoping is enforced in the service layer
    # via (farmer_user_id + farm/crop ids) → uniform 404s, no IDOR oracle.
    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    farm_crop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )

    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # JSON array of opaque extra-image references (images 2–3).
    extra_image_references: Mapped[str | None] = mapped_column(Text, nullable=True)

    # pending → processing → completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="mock-vision")
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Uncertain-language result fields (possible_condition is "X-like
    # symptoms (uncertain)", never a definitive name).
    possible_condition: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    observations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_info_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="mr"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
