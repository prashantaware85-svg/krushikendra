"""Supplier endpoints (thin: RBAC gate → service → response).

Permissions (Step 17 DB RBAC):
- list / get / create → any active staff role.
- update (PUT) → store_manager and up; changing ``is_active`` additionally
  requires admin (403 STORE_ADMIN_REQUIRED otherwise).
- No hard-delete route exists (deactivate via PUT ``is_active`` instead).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.auth import User
from app.models.staff import RBAC_RANK, StoreStaff
from app.modules.staff_access import require_store_staff
from app.modules.suppliers import service
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierOut,
    SupplierPage,
    SupplierUpdate,
)

router = APIRouter(prefix="/store/suppliers", tags=["suppliers"])

StaffCtx = tuple[User, StoreStaff]


@router.get("", response_model=SupplierPage)
def list_suppliers(
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> SupplierPage:
    return service.list_suppliers(db, search=search, limit=limit, offset=offset)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> SupplierOut:
    return SupplierOut.model_validate(service.create_supplier(db, payload))


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> SupplierOut:
    return SupplierOut.model_validate(service.get_supplier(db, supplier_id))


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    staff_ctx: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> SupplierOut:
    """PUT requires manager+; flipping ``is_active`` requires admin."""
    _user, staff = staff_ctx
    if RBAC_RANK.get(staff.role, 0) < RBAC_RANK["store_manager"]:
        raise AppError(
            "Store manager access required.",
            code="STORE_MANAGER_REQUIRED",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data and staff.role != "admin":
        raise AppError(
            "Store admin access required.",
            code="STORE_ADMIN_REQUIRED",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return SupplierOut.model_validate(service.update_supplier(db, supplier_id, payload))
