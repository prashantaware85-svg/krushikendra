"""Farms thin router: auth + DI + status codes only (policy lives in service)."""

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

from app.modules.farms import schemas, service

router = APIRouter(prefix="/api/v1/farms", tags=["farms"])


@router.get("", response_model=list[schemas.FarmRead])
def list_farms(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.FarmRead]:
    return service.list_farms(db, current_user)


@router.post("", response_model=schemas.FarmRead, status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: schemas.FarmCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.FarmRead:
    return service.create_farm(db, current_user, payload)


@router.get("/{farm_id}", response_model=schemas.FarmRead)
def get_farm(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.FarmRead:
    return service.get_farm_detail(db, current_user, farm_id)


@router.put("/{farm_id}", response_model=schemas.FarmRead)
def update_farm(
    farm_id: str,
    payload: schemas.FarmUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.FarmRead:
    return service.update_farm(db, current_user, farm_id, payload)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Response:
    service.delete_farm(db, current_user, farm_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{farm_id}/soil", response_model=schemas.SoilRead)
def get_soil(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.SoilRead:
    return service.get_soil_detail(db, current_user, farm_id)


@router.post("/{farm_id}/soil", response_model=schemas.SoilRead, status_code=status.HTTP_201_CREATED)
def create_soil(
    farm_id: str,
    payload: schemas.SoilCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.SoilRead:
    return service.create_soil(db, current_user, farm_id, payload)


@router.put("/{farm_id}/soil", response_model=schemas.SoilRead)
def update_soil(
    farm_id: str,
    payload: schemas.SoilUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.SoilRead:
    return service.update_soil(db, current_user, farm_id, payload)
