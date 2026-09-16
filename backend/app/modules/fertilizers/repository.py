"""Fertilizer persistence (CRUD only, no policy)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.soil import FertilizerApplication


def create_application(db: Session, **fields) -> FertilizerApplication:
    row = FertilizerApplication(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save(db: Session, row: FertilizerApplication) -> FertilizerApplication:
    db.commit()
    db.refresh(row)
    return row


def _live(query):
    return query.filter(FertilizerApplication.deleted_at.is_(None))


def list_for_crop(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, crop_id: uuid.UUID
) -> list[FertilizerApplication]:
    return (
        _live(
            db.query(FertilizerApplication).filter(
                FertilizerApplication.farmer_user_id == farmer_id,
                FertilizerApplication.farm_id == farm_id,
                FertilizerApplication.farm_crop_id == crop_id,
            )
        )
        .order_by(FertilizerApplication.applied_on.desc())
        .all()
    )


def get_owned(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
) -> FertilizerApplication | None:
    """Owner-scoped fetch (None → caller raises uniform 404, no oracle)."""
    return (
        _live(
            db.query(FertilizerApplication).filter(
                FertilizerApplication.id == application_id,
                FertilizerApplication.farmer_user_id == farmer_id,
                FertilizerApplication.farm_id == farm_id,
                FertilizerApplication.farm_crop_id == crop_id,
            )
        ).first()
    )
