"""Activities thin router: nested CRUD + chronological timeline."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db

try:
    from app.modules.auth.dependencies import get_current_user
except ImportError:  # pragma: no cover - fallback when auth is not restored

    def get_current_user():  # type: ignore[no-redef]
        raise AppError("Authentication is unavailable.", code="NOT_AUTHENTICATED", status_code=401)

from app.modules.activities import schemas, service

router = APIRouter(prefix="/api/v1", tags=["activities"])

_BASE = "/farms/{farm_id}/crops/{crop_id}"


@router.get(_BASE + "/activities", response_model=list[schemas.ActivityRead])
def list_activities(
    farm_id: str,
    crop_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.ActivityRead]:
    return service.list_activities(db, current_user, farm_id, crop_id)


@router.post(
    _BASE + "/activities",
    response_model=schemas.ActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    farm_id: str,
    crop_id: str,
    payload: schemas.ActivityCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.ActivityRead:
    return service.create_activity(db, current_user, farm_id, crop_id, payload)


@router.get(_BASE + "/timeline", response_model=schemas.TimelineRead)
def get_timeline(
    farm_id: str,
    crop_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.TimelineRead:
    return service.get_timeline(db, current_user, farm_id, crop_id)


@router.get(_BASE + "/activities/{activity_id}", response_model=schemas.ActivityRead)
def get_activity(
    farm_id: str,
    crop_id: str,
    activity_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.ActivityRead:
    return service.get_activity_detail(db, current_user, farm_id, crop_id, activity_id)


@router.put(_BASE + "/activities/{activity_id}", response_model=schemas.ActivityRead)
def update_activity(
    farm_id: str,
    crop_id: str,
    activity_id: str,
    payload: schemas.ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.ActivityRead:
    return service.update_activity(db, current_user, farm_id, crop_id, activity_id, payload)


@router.delete(_BASE + "/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    farm_id: str,
    crop_id: str,
    activity_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Response:
    service.delete_activity(db, current_user, farm_id, crop_id, activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
