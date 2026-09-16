"""Farms data access. Every farm query is scoped to one owner + live rows."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.farm import Farm, SoilRecord


def _live_farm_stmt(owner_id: str):
    return (
        select(Farm).where(
            Farm.owner_user_id == owner_id,
            Farm.is_active.is_(True),
            Farm.deleted_at.is_(None),
        )
    )


def list_farms(db: Session, owner_id: str) -> list[Farm]:
    return list(
        db.scalars(_live_farm_stmt(owner_id).order_by(Farm.created_at)).all()
    )


def get_farm(db: Session, farm_id: uuid.UUID | str, owner_id: str) -> Farm | None:
    return db.scalars(
        _live_farm_stmt(owner_id).where(Farm.id == farm_id)
    ).first()


def create_farm(db: Session, **fields) -> Farm:
    farm = Farm(**fields)
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


def update_farm(db: Session, farm: Farm, patch: dict) -> Farm:
    for key, value in patch.items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


def soft_delete_farm(db: Session, farm: Farm) -> None:
    farm.is_active = False
    farm.deleted_at = utcnow()
    db.commit()


def get_soil(db: Session, farm_id: uuid.UUID | str) -> SoilRecord | None:
    return db.scalars(
        select(SoilRecord).where(SoilRecord.farm_id == farm_id)
    ).first()


def create_soil(db: Session, **fields) -> SoilRecord:
    record = SoilRecord(**fields)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_soil(db: Session, record: SoilRecord, patch: dict) -> SoilRecord:
    for key, value in patch.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record
