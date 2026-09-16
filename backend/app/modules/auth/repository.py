"""Auth persistence: CRUD only (users, profiles, OTP + refresh rows). No policy."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import FarmerProfile, OtpVerification, RefreshToken, User


# ── Users ──
def get_user_by_mobile(db: Session, mobile_number: str) -> User | None:
    return db.scalar(select(User).where(User.mobile_number == mobile_number))


def get_user_by_id(db: Session, user_id: str | uuid.UUID) -> User | None:
    try:
        key = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return db.get(User, key)


def create_user(db: Session, mobile_number: str) -> User:
    user = User(mobile_number=mobile_number, is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    return user


# ── Profiles ──
def get_profile_by_user_id(db: Session, user_id: uuid.UUID) -> FarmerProfile | None:
    return db.scalar(select(FarmerProfile).where(FarmerProfile.user_id == user_id))


def create_profile(db: Session, user_id: uuid.UUID) -> FarmerProfile:
    profile = FarmerProfile(user_id=user_id, preferred_language="en")
    db.add(profile)
    db.flush()
    return profile


# ── OTPs ──
def latest_otp(db: Session, mobile_number: str) -> OtpVerification | None:
    """Most recent OTP row for the mobile (consumed or not)."""
    return db.scalar(
        select(OtpVerification)
        .where(OtpVerification.mobile_number == mobile_number)
        .order_by(OtpVerification.created_at.desc())
        .limit(1)
    )


def latest_active_otp(db: Session, mobile_number: str) -> OtpVerification | None:
    """Most recent unconsumed OTP row for the mobile."""
    return db.scalar(
        select(OtpVerification)
        .where(
            OtpVerification.mobile_number == mobile_number,
            OtpVerification.consumed_at.is_(None),
        )
        .order_by(OtpVerification.created_at.desc())
        .limit(1)
    )


def count_recent_otps(db: Session, mobile_number: str, since: datetime) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(OtpVerification)
            .where(
                OtpVerification.mobile_number == mobile_number,
                OtpVerification.created_at >= since,
            )
        )
        or 0
    )


def create_otp(
    db: Session, mobile_number: str, otp_hash: str, expires_at: datetime
) -> OtpVerification:
    row = OtpVerification(
        mobile_number=mobile_number, otp_hash=otp_hash, attempts=0, expires_at=expires_at
    )
    db.add(row)
    db.flush()
    return row


# ── Refresh tokens ──
def create_refresh_token(
    db: Session, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> RefreshToken:
    row = RefreshToken(user_id=user_id, token_hash=token_hash, revoked=False, expires_at=expires_at)
    db.add(row)
    db.flush()
    return row


def get_refresh_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
