"""Health endpoints (thin: auth + validation → service)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.common.dependencies import get_current_farmer_id
from app.modules.health import schemas, service

router = APIRouter(tags=["health"])


# ── Catalogue (reference labels, never a diagnosis) ────────────────────────

@router.get("/pests", response_model=list[schemas.PestDiseaseOut])
def list_pests(
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Active pest rows (verified flag exposed, samples unverified)."""
    return service.list_pests(db)


@router.get("/diseases", response_model=list[schemas.PestDiseaseOut])
def list_diseases(
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Active disease rows (verified flag exposed, samples unverified)."""
    return service.list_diseases(db)


# ── Observations (tracking only) ───────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/crops/{crop_id}/health",
    response_model=list[schemas.HealthObservationOut],
)
def list_observations(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Owned observations, newest first."""
    return service.list_observations(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id
    )


@router.post(
    "/farms/{farm_id}/crops/{crop_id}/health",
    response_model=schemas.HealthObservationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_observation(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    payload: schemas.HealthObservationWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Record field facts verbatim (no diagnosis, no prescriptions)."""
    return service.create_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        payload=payload.model_dump(),
    )


@router.get(
    "/farms/{farm_id}/crops/{crop_id}/health/{observation_id}",
    response_model=schemas.HealthObservationOut,
)
def get_observation(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Owned observation detail."""
    return service.get_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )


@router.put(
    "/farms/{farm_id}/crops/{crop_id}/health/{observation_id}",
    response_model=schemas.HealthObservationOut,
)
def update_observation(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: schemas.HealthObservationWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Plain PUT updates (status transitions included)."""
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    return service.update_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id, patch=patch,
    )


@router.delete(
    "/farms/{farm_id}/crops/{crop_id}/health/{observation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_observation(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Soft-delete (204)."""
    service.delete_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/farms/{farm_id}/crops/{crop_id}/health/{observation_id}/photos",
    response_model=schemas.HealthObservationOut,
)
async def upload_photos(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    photos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Attach up to 3 photos (magic bytes + quality gates)."""
    files = [(p.filename or "photo.jpg", await p.read()) for p in photos]
    return service.upload_photos(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id, files=files,
    )


@router.get("/farms/{farm_id}/crops/{crop_id}/health/{observation_id}/photos/{index}")
def get_photo(
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    index: int,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> FastAPIResponse:
    """Owned photo bytes (authed — no public URLs by design)."""
    data, media_type = service.get_photo_bytes(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id, index=index,
    )
    return FastAPIResponse(content=data, media_type=media_type)


# ── Actions (recorded facts, never system output) ──────────────────────────

@router.get("/health/{observation_id}/actions", response_model=list[schemas.HealthActionOut])
def list_actions(
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Recorded actions for one owned observation."""
    return service.list_actions(db, farmer_id=farmer_id, observation_id=observation_id)


@router.post(
    "/health/{observation_id}/actions",
    response_model=schemas.HealthActionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_action(
    observation_id: uuid.UUID,
    payload: schemas.HealthActionWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Record "what was done"."""
    return service.create_action(
        db, farmer_id=farmer_id, observation_id=observation_id,
        payload=payload.model_dump(),
    )


@router.put(
    "/health/{observation_id}/actions/{action_id}",
    response_model=schemas.HealthActionOut,
)
def update_action(
    observation_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: schemas.HealthActionWrite,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Patch a recorded action."""
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    return service.update_action(
        db, farmer_id=farmer_id, observation_id=observation_id,
        action_id=action_id, patch=patch,
    )


@router.delete(
    "/health/{observation_id}/actions/{action_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_action(
    observation_id: uuid.UUID,
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Soft-delete a recorded action (204)."""
    service.delete_action(
        db, farmer_id=farmer_id, observation_id=observation_id, action_id=action_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
