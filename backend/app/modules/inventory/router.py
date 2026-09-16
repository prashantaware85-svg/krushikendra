"""Inventory endpoints (thin: auth/RBAC → service → response).

Permissions (Step 17 DB RBAC):
- list / detail / summary / low-stock → any authenticated user; farmers see
  only safe availability, staff see internal levels on detail.
- movement history + adjust → any active staff role (403 for non-staff).
- reorder-level (NEW) → store_manager and up (staff get 403).

Reads need auth; farmers see only safe availability (list/detail).
Movement history + adjustments are staff-only (403 for non-staff).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.staff import StoreStaff
from app.modules.auth.dependencies import get_current_user
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    AdjustIn,
    InventoryDetailOut,
    InventoryOut,
    InventoryPage,
    InventorySummaryOut,
    MovementPage,
    ReorderLevelIn,
)
from app.modules.staff_access import (
    is_staff_active,
    require_store_manager,
    require_store_staff,
)

router = APIRouter(prefix="/store/inventory", tags=["inventory"])

StaffCtx = tuple[User, StoreStaff]


@router.get("", response_model=InventoryPage)
def list_inventory(
    product_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    variant_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryPage:
    return service.list_inventory(
        db,
        product_id=product_id,
        category_id=category_id,
        variant_id=variant_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=InventorySummaryOut)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventorySummaryOut:
    return service.get_summary(db)


@router.get("/low-stock", response_model=InventoryPage)
def get_low_stock(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryPage:
    return service.get_low_stock(db, limit=limit, offset=offset)


@router.get("/{variant_id}", response_model=None)
def get_detail(
    variant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InventoryOut | InventoryDetailOut:
    """Staff see internal levels; farmers see safe availability only."""
    return service.get_detail(
        db, variant_id, include_internal=is_staff_active(db, current_user)
    )


@router.get("/{variant_id}/movements", response_model=MovementPage)
def list_movements(
    variant_id: uuid.UUID,
    movement_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> MovementPage:
    return service.list_movements(
        db,
        variant_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post("/{variant_id}/adjust", response_model=InventoryDetailOut)
def adjust_stock(
    variant_id: uuid.UUID,
    payload: AdjustIn,
    staff_ctx: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> InventoryDetailOut:
    return service.adjust_stock(db, staff_ctx[0], variant_id, payload)


@router.put("/{variant_id}/reorder-level", response_model=InventoryDetailOut)
def set_reorder_level(
    variant_id: uuid.UUID,
    payload: ReorderLevelIn,
    _manager: StaffCtx = Depends(require_store_manager),
    db: Session = Depends(get_db),
) -> InventoryDetailOut:
    """Manager-only reorder tuning (staff get 403 STORE_MANAGER_REQUIRED)."""
    return service.set_reorder_level(db, variant_id, payload)
