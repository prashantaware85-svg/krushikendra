"""Crop image endpoints (thin: auth + multipart → service)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.common.dependencies import get_current_farmer_id
from app.modules.vision import schemas, service

router = APIRouter(prefix="/crop-images", tags=["vision"])

_ALLOWED_LANGUAGES = {"mr", "hi", "en"}


@router.post("", response_model=schemas.CropAnalysisOut, status_code=status.HTTP_201_CREATED)
async def upload_crop_images(
    farm_id: uuid.UUID = Form(...),
    crop_id: uuid.UUID | None = Form(default=None),
    language: str = Form(default="mr"),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Upload 1–3 photos → completed observation (sync, uncertain only)."""
    lang = language if language in _ALLOWED_LANGUAGES else "mr"
    files: list[tuple[str, bytes]] = []
    for upload in images:
        files.append((upload.filename or "photo.jpg", await upload.read()))
    return service.upload_and_analyze(
        db,
        farmer_id=farmer_id,
        farm_id=farm_id,
        crop_id=crop_id,
        language=lang,
        files=files,
    )


@router.get("", response_model=list[schemas.AnalysisHistoryItemOut])
def list_analyses(
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Own history, newest, bounded."""
    return service.list_analyses(db, farmer_id=farmer_id)


@router.get("/{analysis_id}", response_model=schemas.CropAnalysisOut)
def get_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Owned result contract (no refs/paths/secrets)."""
    return service.get_analysis(db, farmer_id=farmer_id, analysis_id=analysis_id)


@router.get("/{analysis_id}/image")
def get_image(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> FastAPIResponse:
    """Owned bytes, correct media type (no public URLs by design)."""
    data, media_type = service.get_image_bytes(
        db, farmer_id=farmer_id, analysis_id=analysis_id
    )
    return FastAPIResponse(content=data, media_type=media_type)


@router.post("/{analysis_id}/analyze", response_model=schemas.CropAnalysisOut)
def reanalyze(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Idempotent re-run."""
    return service.reanalyze(db, farmer_id=farmer_id, analysis_id=analysis_id)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Soft-delete the row + remove files (204)."""
    service.delete_analysis(db, farmer_id=farmer_id, analysis_id=analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
