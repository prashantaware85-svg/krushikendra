"""Staff management endpoints (admin-only; thin: gate → service → response)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.staff import StoreStaff
from app.modules.staff import service
from app.modules.staff.schemas import (
    StaffCreate,
    StaffOut,
    StaffPage,
    StaffRoleUpdate,
)
from app.modules.commerce.schemas import OrderItemOut, OrderOut
from app.modules.staff_access import require_store_admin, require_store_staff

router = APIRouter(prefix="/store/staff", tags=["staff"])

AdminCtx = tuple[User, StoreStaff]
StaffCtx = tuple[User, StoreStaff]


@router.get("/orders", response_model=list[OrderOut])
def list_staff_orders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    """Read-only: list ALL orders (any active staff role, store-scoped)."""
    return service.list_all_orders(db, staff[1], limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_staff_order(
    order_id: uuid.UUID,
    staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> OrderOut:
    """Read-only: single order or 404 ORDER_NOT_FOUND."""
    return service.get_staff_order(db, staff[1], order_id)


@router.get("/orders/{order_id}/items", response_model=list[OrderItemOut])
def list_staff_order_items(
    order_id: uuid.UUID,
    staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> list[OrderItemOut]:
    """Read-only: order lines or 404 ORDER_NOT_FOUND."""
    return service.list_staff_order_items(db, staff[1], order_id)


@router.get("", response_model=StaffPage)
def list_staff(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffPage:
    return service.list_staff(db, limit=limit, offset=offset)


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    return service.create_staff(db, admin[0], payload)


@router.get("/{staff_id}", response_model=StaffOut)
def get_staff(
    staff_id: uuid.UUID,
    _admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    return service.get_staff(db, staff_id)


@router.put("/{staff_id}", response_model=StaffOut)
def update_staff(
    staff_id: uuid.UUID,
    payload: StaffRoleUpdate,
    admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    return service.update_staff(db, admin[0], staff_id, payload)


@router.post("/{staff_id}/activate", response_model=StaffOut)
def activate_staff(
    staff_id: uuid.UUID,
    admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    return service.set_active(db, admin[0], staff_id, active=True)


@router.post("/{staff_id}/deactivate", response_model=StaffOut)
def deactivate_staff(
    staff_id: uuid.UUID,
    admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    return service.set_active(db, admin[0], staff_id, active=False)


@router.delete("/{staff_id}", response_model=StaffOut)
def delete_staff(
    staff_id: uuid.UUID,
    admin: AdminCtx = Depends(require_store_admin),
    db: Session = Depends(get_db),
) -> StaffOut:
    """Soft-deactivate (row retained for audit); 200 with ``is_active=False``."""
    return service.delete_staff(db, admin[0], staff_id)
