"""Shared farmer identity dependency.

The auth domain (users table, OTP login) lives outside this rebuild. Every
domain here derives the farmer id SERVER-SIDE from the verified access JWT
(``sub`` claim, ``type == "access"``) — never from path/query/body. Routers
depend ONLY on this; services receive a plain ``uuid.UUID`` (the service
layer never imports FastAPI).
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import AppError

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(message: str = "Authentication required.") -> AppError:
    return AppError(message, code="UNAUTHORIZED", status_code=status.HTTP_401_UNAUTHORIZED)


def get_current_farmer_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    """Return the farmer (user) id from a valid Bearer access token."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired token.") from None
    if payload.get("type") != "access":
        raise _unauthorized("Invalid token type.")
    try:
        return uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError, AttributeError):
        raise _unauthorized("Invalid token subject.") from None
