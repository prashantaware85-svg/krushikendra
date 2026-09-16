"""Staff persistence (store-scoped; no policy here)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.inventory import DEFAULT_STORE_ID
from app.models.staff import ADMIN_ROLE, StoreAuditLog, StoreStaff


def get_staff(db: Session, staff_id: uuid.UUID) -> StoreStaff | None:
    """Store-scoped read: other-store ids surface as None (→ 404, never leak)."""
    stmt = select(StoreStaff).where(
        StoreStaff.store_id == DEFAULT_STORE_ID,
        StoreStaff.id == staff_id,
    )
    return db.scalar(stmt)


def get_by_user(db: Session, user_id: uuid.UUID) -> StoreStaff | None:
    stmt = select(StoreStaff).where(
        StoreStaff.store_id == DEFAULT_STORE_ID,
        StoreStaff.user_id == user_id,
    )
    return db.scalar(stmt)


def count_active_admins(db: Session, *, exclude_staff_id: uuid.UUID | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(StoreStaff)
        .where(
            StoreStaff.store_id == DEFAULT_STORE_ID,
            StoreStaff.role == ADMIN_ROLE,
            StoreStaff.is_active.is_(True),
        )
    )
    if exclude_staff_id is not None:
        stmt = stmt.where(StoreStaff.id != exclude_staff_id)
    return int(db.scalar(stmt) or 0)


def list_staff(db: Session, *, limit: int, offset: int) -> list[StoreStaff]:
    stmt = (
        select(StoreStaff)
        .where(StoreStaff.store_id == DEFAULT_STORE_ID)
        .order_by(StoreStaff.created_at.desc(), StoreStaff.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def count_staff(db: Session) -> int:
    stmt = (
        select(func.count())
        .select_from(StoreStaff)
        .where(StoreStaff.store_id == DEFAULT_STORE_ID)
    )
    return int(db.scalar(stmt) or 0)


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_user_by_mobile(db: Session, mobile: str) -> User | None:
    stmt = select(User).where(User.mobile_number == mobile)
    return db.scalar(stmt)


def write_audit(
    db: Session,
    *,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    action: str,
    old_role: str | None = None,
    new_role: str | None = None,
    old_active: bool | None = None,
    new_active: bool | None = None,
) -> StoreAuditLog:
    row = StoreAuditLog(
        store_id=DEFAULT_STORE_ID,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=action,
        old_role=old_role,
        new_role=new_role,
        old_active=old_active,
        new_active=new_active,
    )
    db.add(row)
    return row
