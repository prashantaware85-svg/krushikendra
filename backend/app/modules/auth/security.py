"""Pure crypto for mobile-OTP auth. No DB access here.

- Mobile normalisation: `+91…` / `91…` / `0…` → 10 digits matching [6-9]xxxxxxxxx.
- OTPs: random digits, stored/compared as HMAC-SHA256 (server JWT secret).
- Access tokens: JWT HS256, 30 min (`sub`=user id, `type`=access).
- Refresh tokens: opaque 48-hex-char values, stored as SHA-256 hex digests.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

import jwt
from fastapi import status

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow

_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def normalize_mobile(raw: str) -> str:
    """Normalise an Indian mobile number or raise 422 AUTH_INVALID_MOBILE."""
    if raw is None or not str(raw).strip():
        raise AppError(
            "Please provide a valid 10-digit mobile number.",
            code="AUTH_INVALID_MOBILE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    cleaned = re.sub(r"[\s\-()]", "", str(raw).strip())
    digits = cleaned
    if digits.startswith("+"):
        if digits.startswith("+91"):
            digits = digits[3:]
        else:
            raise AppError(
                "Only Indian (+91) mobile numbers are supported.",
                code="AUTH_INVALID_MOBILE",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not _MOBILE_RE.fullmatch(digits):
        raise AppError(
            "Please provide a valid 10-digit mobile number.",
            code="AUTH_INVALID_MOBILE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return digits


def generate_otp(length: int = 6) -> str:
    """Cryptographically random numeric OTP (preserves leading zeros)."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(otp: str, secret: str, mobile_number: str = "") -> str:
    """HMAC-SHA256 of the OTP (bound to the mobile number when given)."""
    message = f"{mobile_number}:{otp.strip()}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp_hash(candidate_hash: str, expected_hash: str) -> bool:
    """Constant-time hash comparison (no timing oracle on wrong codes)."""
    return hmac.compare_digest(candidate_hash, expected_hash)


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Only the digest is stored."""
    raw = secrets.token_hex(24)  # 48 hex chars
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def create_access_token(user_id: str, settings: Settings) -> tuple[str, int]:
    """Return (jwt, expires_in_seconds) for an access token."""
    now = utcnow()
    expires_in = settings.access_token_expire_minutes * 60
    expires_at = now + timedelta(seconds=expires_in)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> str:
    """Return the user id (`sub`) or raise 401 with an AUTH_* code."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(
            "Session expired. Please log in again.",
            code="AUTH_TOKEN_EXPIRED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(
            "Invalid access token.",
            code="AUTH_INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if payload.get("type") != "access" or not payload.get("sub"):
        raise AppError(
            "Invalid access token.",
            code="AUTH_INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return str(payload["sub"])
