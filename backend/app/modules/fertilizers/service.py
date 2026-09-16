"""Fertilizer policy: usage records only ("farmer used X").

A record is never a recommendation and never a product-catalogue entry.
Quantities/units are stored verbatim (never converted). Soft-deleted rows
are retained for future expense linkage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.soil import FertilizerApplication
from app.modules.fertilizers import repository


def _not_found() -> AppError:
    return AppError(
        "Fertilizer record not found.",
        code="FERTILIZER_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _serialize(row: FertilizerApplication) -> dict:
    return {
        "id": row.id,
        "farm_crop_id": row.farm_crop_id,
        "application_date": row.applied_on,
        "fertilizer_name": row.fertilizer_name,
        "fertilizer_type": row.fertilizer_type,
        "quantity": None if row.quantity_kg is None else str(row.quantity_kg),
        "quantity_unit": row.quantity_unit,
        "application_method": row.application_method,
        "purpose": row.purpose,
        "notes": row.notes,
    }


def list_applications(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, crop_id: uuid.UUID
) -> list[dict]:
    """Newest-first usage history for one owned crop."""
    return [
        _serialize(row)
        for row in repository.list_for_crop(
            db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id
        )
    ]


def create_application(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    payload: dict,
) -> dict:
    """Record usage (verbatim; nothing computes advice)."""
    payload = dict(payload)
    payload.pop("record_activity", None)  # API parity; no activity module here
    row = repository.create_application(
        db,
        farmer_user_id=farmer_id,
        farm_id=farm_id,
        farm_crop_id=crop_id,
        fertilizer_name=payload["fertilizer_name"],
        fertilizer_type=payload.get("fertilizer_type"),
        quantity_kg=payload.get("quantity"),
        quantity_unit=payload.get("quantity_unit", "kg"),
        application_method=payload.get("application_method"),
        purpose=payload.get("purpose"),
        applied_on=payload["application_date"],
        notes=payload.get("notes"),
    )
    return _serialize(row)


def get_application(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
) -> dict:
    row = repository.get_owned(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id,
    )
    if row is None:
        raise _not_found()
    return _serialize(row)


def update_application(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
    patch: dict,
) -> dict:
    """Patch provided fields (verbatim; never advice)."""
    row = repository.get_owned(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id,
    )
    if row is None:
        raise _not_found()
    mapping = {
        "fertilizer_name": "fertilizer_name",
        "fertilizer_type": "fertilizer_type",
        "quantity": "quantity_kg",
        "quantity_unit": "quantity_unit",
        "application_method": "application_method",
        "purpose": "purpose",
        "application_date": "applied_on",
        "notes": "notes",
    }
    for key, column in mapping.items():
        if key in patch:
            setattr(row, column, patch[key])
    return _serialize(repository.save(db, row))


def delete_application(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
) -> None:
    """Soft-delete (``deleted_at``; rows retained for expense linkage)."""
    row = repository.get_owned(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id,
    )
    if row is None:
        raise _not_found()
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
