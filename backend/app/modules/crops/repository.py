"""Crop data access. Crops resolve ONLY through a live farm the caller owns."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.crop import CropVariety, FarmCrop
from app.models.farm import Farm


def _live_crop_stmt(owner_id: str):
    return (
        select(FarmCrop)
        .join(Farm, Farm.id == FarmCrop.farm_id)
        .where(
            Farm.owner_user_id == owner_id,
            Farm.is_active.is_(True),
            Farm.deleted_at.is_(None),
            FarmCrop.is_active.is_(True),
            FarmCrop.deleted_at.is_(None),
        )
    )


def list_crops(db: Session, farm_id: uuid.UUID | str, owner_id: str) -> list[FarmCrop]:
    return list(
        db.scalars(
            _live_crop_stmt(owner_id)
            .where(FarmCrop.farm_id == farm_id)
            .order_by(FarmCrop.sowing_date, FarmCrop.created_at)
        ).all()
    )


def get_crop(
    db: Session, crop_id: uuid.UUID | str, farm_id: uuid.UUID | str, owner_id: str
) -> FarmCrop | None:
    """Pin BOTH legs: crop must belong to this farm (no cross-pairing)."""
    return db.scalars(
        _live_crop_stmt(owner_id).where(
            FarmCrop.id == crop_id, FarmCrop.farm_id == farm_id
        )
    ).first()


def create_crop(db: Session, **fields) -> FarmCrop:
    crop = FarmCrop(**fields)
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


def update_crop(db: Session, crop: FarmCrop, patch: dict) -> FarmCrop:
    for key, value in patch.items():
        setattr(crop, key, value)
    db.commit()
    db.refresh(crop)
    return crop


def soft_delete_crop(db: Session, crop: FarmCrop) -> None:
    crop.is_active = False
    crop.deleted_at = utcnow()
    db.commit()


def list_varieties(db: Session) -> list[CropVariety]:
    return list(
        db.scalars(
            select(CropVariety)
            .where(CropVariety.is_active.is_(True))
            .order_by(CropVariety.crop_name, CropVariety.variety_name)
        ).all()
    )


def get_variety(db: Session, variety_id: uuid.UUID | str) -> CropVariety | None:
    """Active catalogue rows only (inactive/missing → None)."""
    return db.scalars(
        select(CropVariety).where(
            CropVariety.id == variety_id, CropVariety.is_active.is_(True)
        )
    ).first()
