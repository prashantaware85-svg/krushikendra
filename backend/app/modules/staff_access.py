"""Canonical store-staff RBAC gates (Step 17, DB-backed).

Replaces the interim ``STORE_STAFF_MOBILES`` allowlist: every gate reads the
``store_staff`` table (active rows only) scoped to ``DEFAULT_STORE_ID``
(single store; orders have no ``store_id`` so staff order views stay
farmer-scoped — see router notes).

Role hierarchy (extensible): ``admin > store_manager > store_staff`` via
``RBAC_RANK``. Guards compare ranks, so future roles only need a CHECK
value + a rank entry.

Cross-store reads never leak existence: row lookups filter by
``store_id`` first, so other-store rows surface as 404 ``STORE_*_NOT_FOUND``
(not 403).
"""

from __future__ import annotations

import uuid

from fastapi import Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.auth import User
from app.models.inventory import DEFAULT_STORE_ID
from app.models.staff import RBAC_RANK, StoreStaff
from app.modules.auth.dependencies import get_current_user


def _forbidden(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_403_FORBIDDEN)


def resolve_staff_record(
    db: Session,
    user: User,
    store_id: uuid.UUID = DEFAULT_STORE_ID,
) -> StoreStaff | None:
    """Return the ACTIVE staff row for (store, user), else None (never raises)."""
    stmt = select(StoreStaff).where(
        StoreStaff.store_id == store_id,
        StoreStaff.user_id == user.id,
        StoreStaff.is_active.is_(True),
    )
    return db.scalar(stmt)


def is_staff_active(
    db: Session,
    user: User,
    store_id: uuid.UUID = DEFAULT_STORE_ID,
) -> bool:
    """Non-raising staff check (used to shape farmer-safe reads)."""
    return resolve_staff_record(db, user, store_id) is not None


def _load_any_row(db: Session, user: User) -> StoreStaff | None:
    """Active OR inactive row for this store (to distinguish 403 codes)."""
    stmt = select(StoreStaff).where(
        StoreStaff.store_id == DEFAULT_STORE_ID,
        StoreStaff.user_id == user.id,
    )
    return db.scalar(stmt)


def _require_role(
    db: Session, user: User, minimum_role: str
) -> tuple[User, StoreStaff]:
    row = _load_any_row(db, user)
    if row is None:
        raise _forbidden("STORE_STAFF_REQUIRED", "Store staff access required.")
    if not row.is_active:
        raise _forbidden("STORE_STAFF_INACTIVE", "Store staff access is deactivated.")
    if RBAC_RANK.get(row.role, 0) < RBAC_RANK[minimum_role]:
        if minimum_role == "store_manager":
            raise _forbidden(
                "STORE_MANAGER_REQUIRED", "Store manager access required."
            )
        raise _forbidden("STORE_ADMIN_REQUIRED", "Store admin access required.")
    return user, row


def require_store_staff(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, StoreStaff]:
    """Any active role (store_staff and up). 403 STORE_STAFF_REQUIRED/INACTIVE."""
    return _require_role(db, user, "store_staff")


def require_store_manager(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, StoreStaff]:
    """Admin + store_manager. 403 STORE_STAFF_* or STORE_MANAGER_REQUIRED."""
    return _require_role(db, user, "store_manager")


def require_store_admin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, StoreStaff]:
    """Admin only. 403 STORE_STAFF_* or STORE_ADMIN_REQUIRED."""
    return _require_role(db, user, "admin")
