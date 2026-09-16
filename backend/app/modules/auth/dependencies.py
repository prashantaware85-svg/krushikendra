"""Request-scoped auth dependencies (Bearer access token → active User)."""

from __future__ import annotations

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.auth import User
from app.modules.auth import repository
from app.modules.auth.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the caller from ``Authorization: Bearer <access>`` or raise 401 (AUTH_*).

    Contract relied on by all farmer-scoped domain routers: returns the
    authenticated ``User`` (exposes ``.id``), else raises ``AppError`` with an
    ``AUTH_*`` code (→ 401 envelope, never leaks internals).
    """
    if credentials is None or not credentials.credentials:
        raise AppError(
            "Not authenticated.",
            code="AUTH_MISSING_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    settings = get_settings()
    user_id = decode_access_token(credentials.credentials, settings)
    user = repository.get_user_by_id(db, user_id)
    if user is None:
        raise AppError(
            "User not found.",
            code="AUTH_USER_NOT_FOUND",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        raise AppError(
            "This account is disabled.",
            code="AUTH_USER_INACTIVE",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user
