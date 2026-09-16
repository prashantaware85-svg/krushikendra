"""Supplier policy (store-operational; every route is staff-gated upstream)."""

from __future__ import annotations

import uuid

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.inventory import DEFAULT_STORE_ID, Supplier
from app.modules.suppliers import repository
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierPage,
    SupplierUpdate,
)


def _not_found() -> AppError:
    return AppError(
        "Supplier not found.",
        code="SUPPLIER_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def list_suppliers(
    db: Session, *, search: str | None = None, limit: int = 20, offset: int = 0
) -> SupplierPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = (search or "").strip() or None
    rows = repository.list_suppliers(
        db, DEFAULT_STORE_ID, search=query, limit=limit, offset=offset
    )
    from app.modules.suppliers.schemas import SupplierOut

    return SupplierPage(
        suppliers=[SupplierOut.model_validate(r) for r in rows],
        total=repository.count_suppliers(db, DEFAULT_STORE_ID, search=query),
        limit=limit,
        offset=offset,
    )


def create_supplier(db: Session, payload: SupplierCreate) -> Supplier:
    supplier = Supplier(
        store_id=DEFAULT_STORE_ID,
        name=payload.name,
        mobile_number=(payload.mobile_number or "").strip() or None,
        email=(payload.email or "").strip() or None,
        address=(payload.address or "").strip() or None,
        gstin=payload.gstin,
        notes=(payload.notes or "").strip() or None,
        is_active=payload.is_active,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def get_supplier(db: Session, supplier_id: uuid.UUID) -> Supplier:
    supplier = repository.get_supplier(db, DEFAULT_STORE_ID, supplier_id)
    if supplier is None:
        raise _not_found()
    return supplier


def update_supplier(
    db: Session, supplier_id: uuid.UUID, payload: SupplierUpdate
) -> Supplier:
    """PUT doubles as the active-flag toggle; there is no hard-delete route."""
    supplier = get_supplier(db, supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
            if field in ("mobile_number", "email", "address", "notes") and not value:
                value = None
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
