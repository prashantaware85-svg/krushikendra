"""Fertilizer endpoints (thin: auth + validation → service)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.common.dependencies import get_current_farmer_id
from app.modules.fertilizers import schemas, service

router = APIRouter(
    prefix="/farms/{farm_id}/crops/{crop_id}/fertilizers", tags=["fertilizers"]
)


@router.get("", response_model=list[schemas.FertilizerOut])
def list_applications(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Newest-first usage history for one owned crop."""
    return service.list_applications(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id
    )


@router.post("", response_model=schemas.FertilizerOut, status_code=status.HTTP_201_CREATED)
def create_application(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    payload: schemas.FertilizerWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Record usage (records only — never a recommendation)."""
    return service.create_application(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        payload=payload.model_dump(),
    )


@router.get("/{application_id}", response_model=schemas.FertilizerOut)
def get_application(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Owned usage-record detail."""
    return service.get_application(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id,
    )


@router.put("/{application_id}", response_model=schemas.FertilizerOut)
def update_application(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: schemas.FertilizerWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Patch provided fields."""
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    patch.pop("record_activity", None)
    return service.update_application(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id, patch=patch,
    )


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Soft-delete (204)."""
    service.delete_application(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        application_id=application_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
