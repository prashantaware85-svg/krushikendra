"""Auth policy: expiry, attempts, cooldown, hourly cap, rotation, login."""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import coerce_utc, utcnow
from app.models.auth import User
from app.modules.auth import repository, security, sms

logger = logging.getLogger("krushi-seva.auth")


def request_otp(db: Session, mobile_raw: str, settings: Settings) -> tuple[str, int, str | None]:
    """Issue an OTP challenge. Returns (mobile, resend_after_seconds, dev_otp|None)."""
    mobile = security.normalize_mobile(mobile_raw)
    now = utcnow()

    latest = repository.latest_otp(db, mobile)
    if latest is not None and latest.consumed_at is None:
        elapsed = (now - coerce_utc(latest.created_at)).total_seconds()
        cooldown = settings.otp_resend_cooldown_seconds
        if elapsed < cooldown:
            raise AppError(
                f"Please wait {int(cooldown - elapsed)} seconds before requesting a new OTP.",
                code="OTP_COOLDOWN",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

    sent_last_hour = repository.count_recent_otps(db, mobile, now - timedelta(hours=1))
    if sent_last_hour >= settings.otp_max_sends_per_hour:
        raise AppError(
            "Too many OTP requests. Please try again later.",
            code="OTP_RATE_LIMITED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    otp = security.generate_otp(settings.otp_length)
    otp_hash = security.hash_otp(otp, settings.jwt_secret_key, mobile)
    expires_at = now + timedelta(minutes=settings.otp_expire_minutes)
    repository.create_otp(db, mobile, otp_hash, expires_at)
    db.commit()

    # SMS delivery (Step 3b): real provider when configured; the OTP row is
    # already committed above, so a provider failure leaves a valid row and
    # the farmer simply resends after cooldown. Dev/test without a provider
    # keeps the dev_otp flow below (never in production).
    #
    # TEMPORARY QA path (APK testing only, explicit opt-in): when test mode
    # is on AND this exact mobile is allowlisted, skip the real SMS send —
    # test numbers are not real subscribers. Every other number ALWAYS goes
    # through the provider below (Fast2SMS integration unchanged).
    provider_ref = None
    is_qa_number = settings.otp_test_mode_enabled and mobile in settings.otp_test_mobile_list
    if is_qa_number:
        logger.warning(
            "OTP QA test mode: skipping provider SMS for test mobile ending %s",
            mobile[-4:],
        )
    else:
        provider_ref = sms.send_otp_sms(mobile=mobile, otp=otp, settings=settings)
    if settings.is_production:
        logger.info(
            "OTP SMS accepted for mobile ending %s (provider ref %s)",
            mobile[-4:],
            provider_ref,
        )
    else:
        logger.debug("OTP issued for mobile ending %s", mobile[-4:])

    dev_otp: str | None = None
    if settings.auth_dev_otp_enabled and settings.environment != "production":
        dev_otp = otp
    elif is_qa_number:
        # TEMPORARY QA path: expose the OTP strictly to the allowlisted
        # test number so the APK tester can complete login without real
        # SMS. Production default (flag off) never reaches here, and
        # non-allowlisted numbers never reach here either. Revert the
        # QA env vars immediately after testing.
        logger.warning(
            "OTP QA test mode: exposing dev_otp for test mobile ending %s",
            mobile[-4:],
        )
        dev_otp = otp
    return mobile, settings.otp_resend_cooldown_seconds, dev_otp


def _issue_token_pair(db: Session, user: User, settings: Settings) -> tuple[str, str, int]:
    """Create access JWT + rotated opaque refresh row. Returns (access, raw_refresh, exp_s)."""
    access_token, expires_in = security.create_access_token(str(user.id), settings)
    raw_refresh, refresh_hash = security.generate_refresh_token()
    refresh_expires = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    repository.create_refresh_token(db, user.id, refresh_hash, refresh_expires)
    return access_token, raw_refresh, expires_in


def verify_otp(
    db: Session, mobile_raw: str, otp_raw: str, settings: Settings
) -> tuple[User, bool, str, str, int]:
    """Verify an OTP. Returns (user, is_new_user, access, refresh, expires_in_s)."""
    mobile = security.normalize_mobile(mobile_raw)
    candidate = (otp_raw or "").strip()
    if not candidate:
        raise AppError("Invalid OTP.", code="OTP_INVALID", status_code=status.HTTP_400_BAD_REQUEST)
    now = utcnow()

    row = repository.latest_active_otp(db, mobile)
    if row is None:
        raise AppError(
            "No active OTP found. Please request a fresh OTP.",
            code="OTP_NOT_FOUND",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if now > coerce_utc(row.expires_at):
        # Exhaustion/expiry kills the record — the farmer requests a fresh OTP.
        db.delete(row)
        db.commit()
        raise AppError(
            "OTP has expired. Please request a fresh OTP.",
            code="OTP_EXPIRED",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    expected = security.hash_otp(candidate, settings.jwt_secret_key, mobile)
    if not security.verify_otp_hash(expected, row.otp_hash):
        row.attempts += 1
        if row.attempts >= settings.otp_max_attempts:
            db.delete(row)
            db.commit()
            raise AppError(
                "Too many wrong attempts. Please request a fresh OTP.",
                code="OTP_ATTEMPTS_EXHAUSTED",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        db.commit()
        raise AppError(
            "Invalid OTP. Please try again.",
            code="OTP_INVALID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    row.consumed_at = now
    user = repository.get_user_by_mobile(db, mobile)
    is_new_user = user is None
    if user is None:
        user = repository.create_user(db, mobile)
    elif not user.is_active:
        db.rollback()
        raise AppError(
            "This account is disabled. Please contact support.",
            code="AUTH_USER_INACTIVE",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    else:
        user.is_verified = True
    if repository.get_profile_by_user_id(db, user.id) is None:
        repository.create_profile(db, user.id)
    access_token, raw_refresh, expires_in = _issue_token_pair(db, user, settings)
    db.commit()
    return user, is_new_user, access_token, raw_refresh, expires_in


def refresh_pair(db: Session, refresh_raw: str, settings: Settings) -> tuple[str, str, int]:
    """Rotate an opaque refresh token. Failures are deliberately generic (401)."""
    now = utcnow()
    row = repository.get_refresh_by_hash(db, security.hash_refresh_token(refresh_raw or ""))
    if row is None or row.revoked or now > coerce_utc(row.expires_at):
        raise AppError(
            "Invalid or expired refresh token.",
            code="AUTH_INVALID_REFRESH",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    user = db.get(repository.User, row.user_id)
    if user is None or not user.is_active:
        raise AppError(
            "Invalid or expired refresh token.",
            code="AUTH_INVALID_REFRESH",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    row.revoked = True  # rotation: the presented token dies here
    access_token, new_raw, expires_in = _issue_token_pair(db, user, settings)
    db.commit()
    return access_token, new_raw, expires_in


def logout(db: Session, refresh_raw: str) -> None:
    """Revoke a refresh token. Idempotent — unknown tokens still succeed."""
    token_hash = security.hash_refresh_token(refresh_raw or "")
    row = repository.get_refresh_by_hash(db, token_hash)
    if row is not None and not row.revoked:
        row.revoked = True
        db.commit()
