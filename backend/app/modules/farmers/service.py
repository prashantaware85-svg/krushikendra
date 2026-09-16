"""Farmer profile policy (farmer-scoped; auto-creates the default row)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.auth import FarmerProfile, User
from app.modules.auth import repository as auth_repository
from app.modules.farmers.schemas import FarmerProfileRead, FarmerProfileUpdate


def profile_to_read(profile: FarmerProfile) -> FarmerProfileRead:
    return FarmerProfileRead(
        full_name=profile.full_name,
        preferred_language=profile.preferred_language,  # type: ignore[arg-type]
        state=profile.state,
        district=profile.district,
        taluka=profile.taluka,
        village=profile.village,
    )


def get_profile(db: Session, user: User) -> FarmerProfile:
    """Return the caller's profile, creating the default row if missing."""
    profile = auth_repository.get_profile_by_user_id(db, user.id)
    if profile is None:
        profile = auth_repository.create_profile(db, user.id)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, patch: FarmerProfileUpdate) -> FarmerProfile:
    """Apply a partial update to the caller's profile."""
    profile = get_profile(db, user)
    for field, value in patch.model_dump(exclude_unset=True).items():
        if field == "full_name" and isinstance(value, str):
            value = value.strip()
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
