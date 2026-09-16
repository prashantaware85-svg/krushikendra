"""Supplier persistence (store-scoped; no policy here)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.inventory import Supplier


def get_supplier(db: Session, store_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier | None:
    stmt = select(Supplier).where(
        Supplier.store_id == store_id, Supplier.id == supplier_id
    )
    return db.scalar(stmt)


def count_suppliers(db: Session, store_id: uuid.UUID, *, search: str | None) -> int:
    stmt = select(func.count()).select_from(Supplier).where(Supplier.store_id == store_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Supplier.name.ilike(like), Supplier.mobile_number.ilike(like))
        )
    return int(db.scalar(stmt) or 0)


def list_suppliers(
    db: Session,
    store_id: uuid.UUID,
    *,
    search: str | None,
    limit: int,
    offset: int,
) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.store_id == store_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Supplier.name.ilike(like), Supplier.mobile_number.ilike(like))
        )
    stmt = stmt.order_by(Supplier.created_at.desc(), Supplier.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())
