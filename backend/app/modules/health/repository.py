"""Health persistence (CRUD only, no policy)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.pest import CropHealthObservation, Disease, HealthAction, Pest


def list_catalogue(db: Session, model) -> list:
    return (
        db.query(model)
        .filter(model.is_active.is_(True))
        .order_by(model.name.asc())
        .all()
    )


def get_catalogue_row(db: Session, model, row_id: uuid.UUID):
    return (
        db.query(model)
        .filter(model.id == row_id, model.is_active.is_(True))
        .first()
    )


def catalogue_name(db: Session, model, row_id: uuid.UUID | None) -> str | None:
    if row_id is None:
        return None
    row = db.get(model, row_id)
    return row.name if row is not None else None


def create_observation(db: Session, **fields) -> CropHealthObservation:
    row = CropHealthObservation(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_observation(db: Session, row: CropHealthObservation) -> CropHealthObservation:
    db.commit()
    db.refresh(row)
    return row


def _live_obs(query):
    return query.filter(CropHealthObservation.deleted_at.is_(None))


def list_observations(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, crop_id: uuid.UUID
) -> list[CropHealthObservation]:
    return (
        _live_obs(
            db.query(CropHealthObservation).filter(
                CropHealthObservation.farmer_user_id == farmer_id,
                CropHealthObservation.farm_id == farm_id,
                CropHealthObservation.farm_crop_id == crop_id,
            )
        )
        .order_by(CropHealthObservation.observed_on.desc().nullslast())
        .all()
    )


def get_owned_observation(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
) -> CropHealthObservation | None:
    """Owner-scoped fetch (None → caller raises uniform 404, no oracle)."""
    return (
        _live_obs(
            db.query(CropHealthObservation).filter(
                CropHealthObservation.id == observation_id,
                CropHealthObservation.farmer_user_id == farmer_id,
                CropHealthObservation.farm_id == farm_id,
                CropHealthObservation.farm_crop_id == crop_id,
            )
        ).first()
    )


def get_owned_observation_by_id(
    db: Session, *, farmer_id: uuid.UUID, observation_id: uuid.UUID
) -> CropHealthObservation | None:
    """Owner-scoped fetch without the farm/crop legs (action routes)."""
    return (
        _live_obs(
            db.query(CropHealthObservation).filter(
                CropHealthObservation.id == observation_id,
                CropHealthObservation.farmer_user_id == farmer_id,
            )
        ).first()
    )


def create_action(db: Session, **fields) -> HealthAction:
    row = HealthAction(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_action(db: Session, row: HealthAction) -> HealthAction:
    db.commit()
    db.refresh(row)
    return row


def list_actions(db: Session, *, observation_id: uuid.UUID) -> list[HealthAction]:
    return (
        db.query(HealthAction)
        .filter(
            HealthAction.observation_id == observation_id,
            HealthAction.deleted_at.is_(None),
        )
        .order_by(HealthAction.acted_on.desc().nullslast())
        .all()
    )


def get_owned_action(
    db: Session, *, observation_id: uuid.UUID, action_id: uuid.UUID
) -> HealthAction | None:
    return (
        db.query(HealthAction)
        .filter(
            HealthAction.id == action_id,
            HealthAction.observation_id == observation_id,
            HealthAction.deleted_at.is_(None),
        )
        .first()
    )
