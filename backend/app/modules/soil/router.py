"""Soil-test endpoints (thin: auth + validation → service)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.common.dependencies import get_current_farmer_id
from app.modules.soil import schemas, service

router = APIRouter(prefix="/farms/{farm_id}/soil-tests", tags=["soil"])


@router.get("", response_model=list[schemas.SoilTestOut])
def list_tests(
    farm_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Newest-first history for one owned farm."""
    return service.list_tests(db, farmer_id=farmer_id, farm_id=farm_id)


@router.post("", response_model=schemas.SoilTestOut, status_code=status.HTTP_201_CREATED)
def create_test(
    farm_id: uuid.UUID,
    payload: schemas.SoilTestWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Record farmer-provided values (never converted, never advised on)."""
    return service.create_test(
        db, farmer_id=farmer_id, farm_id=farm_id, payload=payload.model_dump()
    )


@router.get("/{test_id}", response_model=schemas.SoilTestOut)
def get_test(
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Owned test detail (``has_report`` only — bytes via report route)."""
    return service.get_test(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)


@router.put("/{test_id}", response_model=schemas.SoilTestOut)
def update_test(
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    payload: schemas.SoilTestWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Patch provided fields."""
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    return service.update_test(
        db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id, patch=patch
    )


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test(
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Soft-delete (204)."""
    service.delete_test(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{test_id}/report", response_model=schemas.SoilTestOut)
async def upload_report(
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    report: UploadFile = File(...),
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Attach a PDF/JPG/PNG report (validated by magic bytes, size-capped)."""
    return service.upload_report(
        db,
        farmer_id=farmer_id,
        farm_id=farm_id,
        test_id=test_id,
        filename=report.filename or "report",
        data=await report.read(),
    )


@router.get("/{test_id}/report")
def get_report(
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> FastAPIResponse:
    """Owned report bytes (authed — no public URLs by design)."""
    data, media_type = service.get_report_bytes(
        db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id
    )
    return FastAPIResponse(content=data, media_type=media_type)
