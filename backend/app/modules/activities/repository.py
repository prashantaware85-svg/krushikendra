"""Activity data access. Rows resolve ONLY via crop → farm → owner JOIN chain."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.activity import FarmActivity
from app.models.crop import FarmCrop
from app.models.farm import Farm


def _live_activity_stmt(owner_id: str):
    return (
        select(FarmActivity)
        .join(FarmCrop, FarmCrop.id == FarmActivity.farm_crop_id)
        .join(Farm, Farm.id == FarmCrop.farm_id)
        .where(
            Farm.owner_user_id == owner_id,
            Farm.is_active.is_(True),
            Farm.deleted_at.is_(None),
            FarmCrop.is_active.is_(True),
            FarmCrop.deleted_at.is_(None),
            FarmActivity.is_active.is_(True),
            FarmActivity.deleted_at.is_(None),
        )
    )


def _chronological(stmt):
    return stmt.order_by(FarmActivity.activity_date, FarmActivity.created_at)


def list_activities(
    db: Session,
    crop_id: uuid.UUID | str,
    farm_id: uuid.UUID | str,
    owner_id: str,
) -> list[FarmActivity]:
    return list(
        db.scalars(
            _chronological(
                _live_activity_stmt(owner_id).where(
                    FarmActivity.farm_crop_id == crop_id,
                    FarmCrop.farm_id == farm_id,
                )
            )
        ).all()
    )


def get_activity(
    db: Session,
    activity_id: uuid.UUID | str,
    crop_id: uuid.UUID | str,
    farm_id: uuid.UUID | str,
    owner_id: str,
) -> FarmActivity | None:
    """Pin all three legs (farm + crop + activity) to defeat URL pairing tricks."""
    return db.scalars(
        _live_activity_stmt(owner_id).where(
            FarmActivity.id == activity_id,
            FarmActivity.farm_crop_id == crop_id,
            FarmCrop.farm_id == farm_id,
        )
    ).first()


def create_activity(db: Session, **fields) -> FarmActivity:
    activity = FarmActivity(**fields)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def update_activity(db: Session, activity: FarmActivity, patch: dict) -> FarmActivity:
    for key, value in patch.items():
        setattr(activity, key, value)
    db.commit()
    db.refresh(activity)
    return activity


def soft_delete_activity(db: Session, activity: FarmActivity) -> None:
    activity.is_active = False
    activity.deleted_at = utcnow()
    db.commit()
