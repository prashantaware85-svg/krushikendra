"""Farmer profile endpoints (thin: auth → service → response)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.farmers import service
from app.modules.farmers.schemas import FarmerProfileRead, FarmerProfileUpdate

router = APIRouter(prefix="/farmer", tags=["farmers"])


@router.get("/profile", response_model=FarmerProfileRead)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FarmerProfileRead:
    return service.profile_to_read(service.get_profile(db, current_user))


@router.put("/profile", response_model=FarmerProfileRead)
def update_profile(
    patch: FarmerProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FarmerProfileRead:
    return service.profile_to_read(service.update_profile(db, current_user, patch))
