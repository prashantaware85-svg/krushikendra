"""Auth endpoints (thin: validate → service → response)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.auth import repository, service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    SendOtpRequest,
    SendOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.models.auth import User
from app.modules.farmers.schemas import FarmerProfileRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(payload: SendOtpRequest, db: Session = Depends(get_db)) -> SendOtpResponse:
    settings = get_settings()
    mobile, resend_after, dev_otp = service.request_otp(db, payload.mobile_number, settings)
    return SendOtpResponse(
        message="OTP sent successfully.",
        mobile_number=mobile,
        resend_after_seconds=resend_after,
        dev_otp=dev_otp,
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)) -> VerifyOtpResponse:
    settings = get_settings()
    _, is_new_user, access_token, raw_refresh, expires_in = service.verify_otp(
        db, payload.mobile_number, payload.otp, settings
    )
    return VerifyOtpResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in_seconds=expires_in,
        is_new_user=is_new_user,
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> RefreshResponse:
    settings = get_settings()
    access_token, new_raw, expires_in = service.refresh_pair(db, payload.refresh_token, settings)
    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_raw,
        token_type="bearer",
        expires_in_seconds=expires_in,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> LogoutResponse:
    service.logout(db, payload.refresh_token)
    return LogoutResponse()


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    profile = repository.get_profile_by_user_id(db, current_user.id)
    return {
        "id": str(current_user.id),
        "mobile_number": current_user.mobile_number,
        "is_verified": current_user.is_verified,
        "profile": (
            FarmerProfileRead(
                full_name=profile.full_name,
                preferred_language=profile.preferred_language,  # type: ignore[arg-type]
                state=profile.state,
                district=profile.district,
                taluka=profile.taluka,
                village=profile.village,
            ).model_dump()
            if profile is not None
            else None
        ),
    }
