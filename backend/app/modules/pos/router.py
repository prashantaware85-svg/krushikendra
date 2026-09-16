"""POS counter-billing endpoints (thin: RBAC gate → service → response).

Permissions (Step 18, DB RBAC):
- products / bills create+list+get / complete / receipt / summary →
  any active staff role (403 for non-staff).
- cancel → store_manager and up (staff get 403 STORE_MANAGER_REQUIRED).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.staff import StoreStaff
from app.modules.pos import service
from app.modules.pos.schemas import (
    PosBillCancelIn,
    PosBillCancelOut,
    PosBillCompleteIn,
    PosBillCompleteOut,
    PosBillCreate,
    PosBillOut,
    PosBillPage,
    PosProductOut,
    PosReceiptOut,
    PosSummaryOut,
)
from app.modules.staff_access import require_store_manager, require_store_staff

router = APIRouter(prefix="/store/pos", tags=["pos"])

StaffCtx = tuple[User, StoreStaff]


@router.get("/products", response_model=list[PosProductOut])
def list_products(
    search: str | None = Query(default=None, max_length=120),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> list[PosProductOut]:
    return service.list_products(db, search=search)


@router.get("/products/{variant_id}", response_model=PosProductOut)
def get_product(
    variant_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosProductOut:
    return service.get_product(db, variant_id)


@router.post("/bills", response_model=PosBillOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: PosBillCreate,
    staff_ctx: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosBillOut:
    return service.create_bill(db, staff_ctx[0], staff_ctx[1], payload)


@router.get("/bills", response_model=PosBillPage)
def list_bills(
    bill_number: str | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    payment_mode: str | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    sale_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosBillPage:
    return service.list_bills(
        db,
        bill_number=bill_number,
        customer_id=customer_id,
        payment_mode=payment_mode,
        payment_status=payment_status,
        sale_status=sale_status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=PosSummaryOut)
def get_summary(
    day: date | None = Query(default=None),
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosSummaryOut:
    return service.get_summary(db, day)


@router.get("/bills/{bill_id}", response_model=PosBillOut)
def get_bill(
    bill_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosBillOut:
    return service.get_bill(db, bill_id)


@router.post("/bills/{bill_id}/complete", response_model=PosBillCompleteOut)
def complete_bill(
    bill_id: uuid.UUID,
    payload: PosBillCompleteIn,
    staff_ctx: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosBillCompleteOut:
    return service.complete_bill(db, staff_ctx[0], bill_id, payload)


@router.post("/bills/{bill_id}/cancel", response_model=PosBillCancelOut)
def cancel_bill(
    bill_id: uuid.UUID,
    payload: PosBillCancelIn | None = None,
    manager_ctx: StaffCtx = Depends(require_store_manager),
    db: Session = Depends(get_db),
) -> PosBillCancelOut:
    reason = payload.reason if payload is not None else None
    out = service.cancel_bill(db, manager_ctx[0], bill_id, reason)
    return PosBillCancelOut(bill=out.bill, duplicate=out.duplicate)


@router.get("/bills/{bill_id}/receipt", response_model=PosReceiptOut)
def get_receipt(
    bill_id: uuid.UUID,
    _staff: StaffCtx = Depends(require_store_staff),
    db: Session = Depends(get_db),
) -> PosReceiptOut:
    return service.get_receipt(db, bill_id)
