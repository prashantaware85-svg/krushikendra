"""Activity policy: crop-leg scoping first, then activity-leg; timeline = chronological."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import coerce_utc
from app.models.activity import FarmActivity
from app.modules.activities import repository, schemas
from app.modules.crops import service as crops_service
from app.modules.farms import service as farms_service


def _uid(user: Any) -> str:
    return str(user.id)


def _parse_date(value: date | str | None, *, field: str) -> date:
    if isinstance(value, date):
        return value
    if value not in (None, ""):
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            pass
    raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)


def _money(value: Any, *, field: str, minimum: float = 0.0) -> float | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)
    if amount < Decimal(str(minimum)) or (field == "quantity" and amount <= 0):
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)
    return float(amount)


def to_activity_read(activity: FarmActivity) -> schemas.ActivityRead:
    created = coerce_utc(activity.created_at) if activity.created_at else None
    return schemas.ActivityRead(
        id=str(activity.id),
        farm_crop_id=str(activity.farm_crop_id),
        activity_type=activity.activity_type,
        title=activity.title,
        description=activity.description,
        activity_date=activity.activity_date.isoformat(),
        status=activity.status,
        quantity=None if activity.quantity is None else str(activity.quantity),
        quantity_unit=activity.quantity_unit,
        cost=None if activity.cost_amount is None else str(activity.cost_amount),
        notes=activity.notes,
        created_at=created.isoformat() if created else None,
    )


def resolve_activity(db: Session, user: Any, farm_id: str, crop_id: str, activity_id: str) -> FarmActivity:
    """Farm leg → crop leg → activity leg, each with its own uniform 404."""
    crop = crops_service.resolve_crop(db, user, farm_id, crop_id)
    activity = repository.get_activity(
        db,
        farms_service.parse_uuid(
            activity_id, code="ACTIVITY_NOT_FOUND", message="Activity not found."
        ),
        crop.id,
        crop.farm_id,
        _uid(user),
    )
    if activity is None:
        raise AppError("Activity not found.", code="ACTIVITY_NOT_FOUND", status_code=404)
    return activity


def list_activities(db: Session, user: Any, farm_id: str, crop_id: str) -> list[schemas.ActivityRead]:
    crop = crops_service.resolve_crop(db, user, farm_id, crop_id)
    rows = repository.list_activities(db, crop.id, crop.farm_id, _uid(user))
    return [to_activity_read(a) for a in rows]


def create_activity(
    db: Session, user: Any, farm_id: str, crop_id: str, payload: schemas.ActivityCreate
) -> schemas.ActivityRead:
    crop = crops_service.resolve_crop(db, user, farm_id, crop_id)
    if not (payload.title or "").strip():
        raise AppError("title is required.", code="VALIDATION_ERROR", status_code=422)
    cost = payload.cost if payload.cost is not None else payload.cost_amount
    activity = repository.create_activity(
        db,
        farm_crop_id=crop.id,
        activity_type=payload.activity_type,
        title=payload.title.strip(),
        description=payload.description,
        activity_date=_parse_date(payload.activity_date, field="activity_date"),
        status=payload.status,
        quantity=_money(payload.quantity, field="quantity"),
        quantity_unit=payload.quantity_unit,
        cost_amount=_money(cost, field="cost"),
        notes=payload.notes,
    )
    return to_activity_read(activity)


def get_activity_detail(
    db: Session, user: Any, farm_id: str, crop_id: str, activity_id: str
) -> schemas.ActivityRead:
    return to_activity_read(resolve_activity(db, user, farm_id, crop_id, activity_id))


def update_activity(
    db: Session, user: Any, farm_id: str, crop_id: str, activity_id: str,
    payload: schemas.ActivityUpdate,
) -> schemas.ActivityRead:
    activity = resolve_activity(db, user, farm_id, crop_id, activity_id)
    data = payload.model_dump(exclude_unset=True)
    patch: dict = {}
    for field in ("activity_type", "description", "status", "quantity_unit", "notes"):
        if field in data:
            patch[field] = data[field]
    if "title" in data and data["title"] is not None:
        if not data["title"].strip():
            raise AppError("title cannot be empty.", code="VALIDATION_ERROR", status_code=422)
        patch["title"] = data["title"].strip()
    if "activity_date" in data:
        patch["activity_date"] = _parse_date(data["activity_date"], field="activity_date")
    if "quantity" in data:
        patch["quantity"] = _money(data["quantity"], field="quantity")
    if "cost" in data or "cost_amount" in data:
        raw = data.get("cost", None)
        if raw is None:
            raw = data.get("cost_amount")
        patch["cost_amount"] = _money(raw, field="cost")
    activity = repository.update_activity(db, activity, patch)
    return to_activity_read(activity)


def delete_activity(db: Session, user: Any, farm_id: str, crop_id: str, activity_id: str) -> None:
    repository.soft_delete_activity(db, resolve_activity(db, user, farm_id, crop_id, activity_id))


def get_timeline(db: Session, user: Any, farm_id: str, crop_id: str) -> schemas.TimelineRead:
    crop = crops_service.resolve_crop(db, user, farm_id, crop_id)
    rows = repository.list_activities(db, crop.id, crop.farm_id, _uid(user))
    return schemas.TimelineRead(
        farm_id=str(crop.farm_id),
        crop_id=str(crop.id),
        crop_name=crop.crop_name,
        activities=[to_activity_read(a) for a in rows],
    )
