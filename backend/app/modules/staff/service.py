"""Staff RBAC policy (admin-only management + last-admin guard).

Rules:
- Only ``admin`` can list/create/change-roles/activate/deactivate/delete.
  (Enforced at the router via ``require_store_admin``; service re-checks
  nothing about the caller — it trusts the gate and records the actor.)
- Resolving the target user by mobile (normalised) or user_id; 404
  STAFF_USER_NOT_FOUND when no such login user exists (never creates login
  accounts).
- Last-active-admin guard: demoting / deactivating / deleting the final
  active admin is refused with 422 LAST_ADMIN_REQUIRED.
- DELETE is a soft-deactivate (``is_active=False``) + audit action
  ``delete``; the row stays for audit history. Returns the row with
  ``active=False`` and HTTP 200.
- Every mutation writes one ``StoreAuditLog`` row in the SAME transaction
  (actor/target/old/new/timestamp; never secrets).
"""

from __future__ import annotations

import uuid

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import User
from app.models.commerce import Order
from app.models.inventory import DEFAULT_STORE_ID
from app.models.staff import ADMIN_ROLE, StoreStaff
from app.modules.auth.security import normalize_mobile
from app.modules.commerce import service as commerce_service
from app.modules.commerce.schemas import OrderItemOut, OrderOut
from app.modules.staff import repository
from app.modules.staff.schemas import StaffCreate, StaffOut, StaffPage, StaffRoleUpdate


def _not_found(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


def _unprocessable(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def _conflict(message: str) -> AppError:
    return AppError(message, code="STAFF_ALREADY_EXISTS", status_code=status.HTTP_409_CONFLICT)


def _last_admin_guard(db: Session, row: StoreStaff) -> None:
    """Refuse to remove the final active admin's admin-active status."""
    if row.role == ADMIN_ROLE and row.is_active:
        remaining = repository.count_active_admins(db, exclude_staff_id=row.id)
        if remaining == 0:
            raise _unprocessable(
                "LAST_ADMIN_REQUIRED",
                "Cannot remove the last active admin.",
            )


def _to_out(db: Session, row: StoreStaff) -> StaffOut:
    user = repository.get_user_by_id(db, row.user_id)
    mobile = user.mobile_number if user is not None else None
    display_name = None
    if user is not None:
        profile = user.profile
        if profile is not None:
            display_name = profile.full_name
    return StaffOut(
        id=row.id,
        user_id=row.user_id,
        mobile=mobile,
        display_name=display_name,
        role=row.role,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _resolve_target_user(db: Session, payload: StaffCreate) -> User:
    if payload.user_id is not None:
        user = repository.get_user_by_id(db, payload.user_id)
        if user is None:
            raise _not_found("STAFF_USER_NOT_FOUND", "No login user for this staff entry.")
        return user
    if payload.mobile_number is not None and payload.mobile_number.strip():
        mobile = normalize_mobile(payload.mobile_number)
        user = repository.get_user_by_mobile(db, mobile)
        if user is None:
            raise _not_found("STAFF_USER_NOT_FOUND", "No login user for this staff entry.")
        return user
    raise _unprocessable(
        "STAFF_IDENTITY_REQUIRED",
        "Provide mobile_number or user_id of an existing login user.",
    )


def list_staff(db: Session, *, limit: int = 20, offset: int = 0) -> StaffPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    rows = repository.list_staff(db, limit=limit, offset=offset)
    return StaffPage(
        staff=[_to_out(db, r) for r in rows],
        total=repository.count_staff(db),
        limit=limit,
        offset=offset,
    )


def create_staff(db: Session, actor: User, payload: StaffCreate) -> StaffOut:
    """Create a staff row (admin CAN create admins). First admin needs no guard."""
    target = _resolve_target_user(db, payload)
    if repository.get_by_user(db, target.id) is not None:
        raise _conflict("This user is already store staff.")
    row = StoreStaff(
        store_id=DEFAULT_STORE_ID,
        user_id=target.id,
        role=payload.role,
        is_active=True,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _conflict("This user is already store staff.") from exc
    repository.write_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=target.id,
        action="staff_create",
        old_role=None,
        new_role=row.role,
        old_active=None,
        new_active=True,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _conflict("This user is already store staff.") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(row)
    return _to_out(db, row)


def get_staff(db: Session, staff_id: uuid.UUID) -> StaffOut:
    row = repository.get_staff(db, staff_id)
    if row is None:
        raise _not_found("STAFF_NOT_FOUND", "Staff entry not found.")
    return _to_out(db, row)


def update_staff(
    db: Session, actor: User, staff_id: uuid.UUID, payload: StaffRoleUpdate
) -> StaffOut:
    """Role change and/or active toggle (last-admin guard on demote/deactivate)."""
    row = repository.get_staff(db, staff_id)
    if row is None:
        raise _not_found("STAFF_NOT_FOUND", "Staff entry not found.")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _to_out(db, row)
    old_role, old_active = row.role, row.is_active
    new_role = data.get("role", row.role)
    new_active = data.get("is_active", row.is_active)
    demoting_admin = old_role == ADMIN_ROLE and new_role != ADMIN_ROLE
    deactivating = old_active and new_active is False
    if (demoting_admin or deactivating) and old_active and old_role == ADMIN_ROLE:
        _last_admin_guard(db, row)
    row.role = new_role
    row.is_active = bool(new_active)
    action = "role_change" if new_role != old_role else (
        "activate" if new_active and not old_active else "deactivate"
    )
    repository.write_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=row.user_id,
        action=action,
        old_role=old_role,
        new_role=row.role,
        old_active=old_active,
        new_active=row.is_active,
    )
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


def set_active(
    db: Session, actor: User, staff_id: uuid.UUID, *, active: bool
) -> StaffOut:
    row = repository.get_staff(db, staff_id)
    if row is None:
        raise _not_found("STAFF_NOT_FOUND", "Staff entry not found.")
    if row.is_active == active:
        return _to_out(db, row)
    if not active:
        _last_admin_guard(db, row)
    old_active = row.is_active
    row.is_active = active
    repository.write_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=row.user_id,
        action="activate" if active else "deactivate",
        old_role=row.role,
        new_role=row.role,
        old_active=old_active,
        new_active=active,
    )
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


def delete_staff(db: Session, actor: User, staff_id: uuid.UUID) -> StaffOut:
    """DELETE = soft-deactivate + audit action ``delete`` (row retained).

    Hard delete is avoided so audit rows keep their meaning; the response
    is HTTP 200 with ``is_active=False``. Last-admin guard applies.
    """
    row = repository.get_staff(db, staff_id)
    if row is None:
        raise _not_found("STAFF_NOT_FOUND", "Staff entry not found.")
    _last_admin_guard(db, row)
    old_active = row.is_active
    row.is_active = False
    repository.write_audit(
        db,
        actor_user_id=actor.id,
        target_user_id=row.user_id,
        action="delete",
        old_role=row.role,
        new_role=row.role,
        old_active=old_active,
        new_active=False,
    )
    db.commit()
    db.refresh(row)
    return _to_out(db, row)


# ── Staff read-only store order view ────────────────────────────────────
def _ensure_store_scope(staff: StoreStaff) -> None:
    """Single-store scope: staff row must belong to DEFAULT_STORE_ID.

    Orders carry no ``store_id`` (single store); scope is enforced on the
    staff row so cross-store rows never leak existence (404, not 403).
    """
    if staff.store_id != DEFAULT_STORE_ID:
        raise _not_found("STORE_NOT_IN_SCOPE", "Store not in scope.")


def list_all_orders(
    db: Session, staff: StoreStaff, *, limit: int = 20, offset: int = 0
) -> list[OrderOut]:
    """List ALL orders (read-only, any active staff role). No store_id param."""
    _ensure_store_scope(staff)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    stmt = (
        select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    )
    rows = list(db.scalars(stmt).all())
    return [commerce_service.order_to_out(db, o) for o in rows]


def get_staff_order(
    db: Session, staff: StoreStaff, order_id: uuid.UUID
) -> OrderOut:
    """Single order (read-only) or 404 ORDER_NOT_FOUND."""
    _ensure_store_scope(staff)
    order = db.get(Order, order_id)
    if order is None:
        raise _not_found("ORDER_NOT_FOUND", "Order not found.")
    return commerce_service.order_to_out(db, order)


def list_staff_order_items(
    db: Session, staff: StoreStaff, order_id: uuid.UUID
) -> list[OrderItemOut]:
    """Order lines (read-only) or 404 ORDER_NOT_FOUND."""
    return get_staff_order(db, staff, order_id).items
