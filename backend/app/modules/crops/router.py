"""Crops thin router: nested plantings + global variety catalogue."""

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

from app.modules.crops import schemas, service

router = APIRouter(prefix="/api/v1", tags=["crops"])


@router.get("/farms/{farm_id}/crops", response_model=list[schemas.CropRead])
def list_crops(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.CropRead]:
    return service.list_crops(db, current_user, farm_id)


@router.post(
    "/farms/{farm_id}/crops", response_model=schemas.CropRead, status_code=status.HTTP_201_CREATED
)
def create_crop(
    farm_id: str,
    payload: schemas.CropCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.CropRead:
    return service.create_crop(db, current_user, farm_id, payload)


@router.get("/farms/{farm_id}/crops/{crop_id}", response_model=schemas.CropRead)
def get_crop(
    farm_id: str,
    crop_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.CropRead:
    return service.get_crop_detail(db, current_user, farm_id, crop_id)


@router.put("/farms/{farm_id}/crops/{crop_id}", response_model=schemas.CropRead)
def update_crop(
    farm_id: str,
    crop_id: str,
    payload: schemas.CropUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.CropRead:
    return service.update_crop(db, current_user, farm_id, crop_id, payload)


@router.delete("/farms/{farm_id}/crops/{crop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crop(
    farm_id: str,
    crop_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Response:
    service.delete_crop(db, current_user, farm_id, crop_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/crop-varieties", response_model=list[schemas.CropVarietyRead])
def list_varieties(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.CropVarietyRead]:
    return service.list_varieties(db)


@router.get("/crop-varieties/{variety_id}", response_model=schemas.CropVarietyRead)
def get_variety(
    variety_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.CropVarietyRead:
    return service.get_variety_detail(db, variety_id)
