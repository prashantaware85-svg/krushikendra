"""Shared store-staff gate (Step 16 interim authorization) — DEPRECATED shim.

Step 17 replaced the ``settings.store_staff_mobiles`` allowlist with
DB-backed RBAC (``store_staff`` table). This module is kept as a thin shim
delegating to :mod:`app.modules.staff_access` so existing imports keep
working; new code MUST import from ``app.modules.staff_access`` directly.

The legacy ``store_staff_mobiles`` setting remains in config (harmless,
documented legacy) but is NO LONGER consulted for authorization anywhere.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.staff import StoreStaff
from app.modules.auth.dependencies import get_current_user
from app.modules.staff_access import (
    is_staff_active as _is_staff_active,
)
from app.modules.staff_access import (
    require_store_admin,
    require_store_manager,
    require_store_staff as _require_store_staff,
)

__all__ = [
    "staff_allowlist",
    "is_store_staff",
    "require_store_staff",
    "require_store_manager",
    "require_store_admin",
]


def staff_allowlist() -> set[str]:
    """Legacy allowlist parser — DEPRECATED, always empty, never authoritative.

    Kept so old imports don't break. Authorization MUST use the
    ``store_staff`` table via :mod:`app.modules.staff_access`.
    """
    return set()


def is_store_staff(user: User, db: Session | None = None) -> bool:
    """Deprecated non-raising check; delegates to DB RBAC when ``db`` given.

    Without a session the answer is fail-closed (False) — the allowlist is
    no longer consulted. Callers with a request DB should prefer
    ``staff_access.is_staff_active(db, user)``.
    """
    if db is None:
        return False
    return _is_staff_active(db, user)


def require_store_staff(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, StoreStaff]:
    """Deprecated shim — delegates to ``staff_access.require_store_staff``."""
    return _require_store_staff(user, db)
