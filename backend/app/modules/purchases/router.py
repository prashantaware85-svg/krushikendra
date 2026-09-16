"""Purchase endpoints (thin: RBAC gate → service → response).

Permissions (Step 17 DB RBAC):
- create / list / get / edit (items add/remove, draft update) / receive →
  any active staff role.
- cancel → store_manager and up (staff get 403 STORE_MANAGER_REQUIRED).
- received purchases stay immutable (existing service rule, unchanged).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.staff import StoreStaff
from app.modules.staff_access import require_store_manager, require_store_staff
from app.modules.purchases import service
from app.modules.purchases.schemas import (
    PurchaseActionOut,
    PurchaseCreate,
    PurchaseItemCreate,
    PurchaseItemOut,
    PurchaseOut,
    PurchasePage,
    PurchaseUpdate,
)

router = APIRouter(prefix="/store/purchases", tags=["purchases"])

StaffCtx = tuple[User, StoreStaff]


@router.post("", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    staff_ctx: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseOut:
    return service.create_purchase(db, staff_ctx[0], payload)


@router.get("", response_model=PurchasePage)
def list_purchases(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchasePage:
    return service.list_purchases(db, status_filter=status_filter, limit=limit, offset=offset)


@router.get("/{purchase_id}", response_model=PurchaseOut)
def get_purchase(
    purchase_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseOut:
    return service.get_purchase(db, purchase_id)


@router.put("/{purchase_id}", response_model=PurchaseOut)
def update_purchase(
    purchase_id: uuid.UUID,
    payload: PurchaseUpdate,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseOut:
    return service.update_purchase(db, purchase_id, payload)


@router.get("/{purchase_id}/items", response_model=list[PurchaseItemOut])
def list_purchase_items(
    purchase_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> list[PurchaseItemOut]:
    return service.list_items(db, purchase_id)


@router.post(
    "/{purchase_id}/items",
    response_model=PurchaseItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_purchase_item(
    purchase_id: uuid.UUID,
    payload: PurchaseItemCreate,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseItemOut:
    return service.add_item(db, purchase_id, payload)


@router.delete("/{purchase_id}/items/{item_id}", response_model=PurchaseOut)
def remove_purchase_item(
    purchase_id: uuid.UUID,
    item_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseOut:
    return service.remove_item(db, purchase_id, item_id)


@router.post("/{purchase_id}/receive", response_model=PurchaseActionOut)
def receive_purchase(
    purchase_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PurchaseActionOut:
    return service.receive_purchase(db, purchase_id)


@router.post("/{purchase_id}/cancel", response_model=PurchaseActionOut)
def cancel_purchase(
    purchase_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_manager),
    db: Session = Depends(get_db),
) -> PurchaseActionOut:
    return service.cancel_purchase(db, purchase_id)
