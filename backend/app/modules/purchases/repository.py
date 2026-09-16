"""Purchase persistence (store-scoped; no policy here)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import Purchase, PurchaseItem, Supplier


def get_purchase(db: Session, store_id: uuid.UUID, purchase_id: uuid.UUID) -> Purchase | None:
    stmt = select(Purchase).where(
        Purchase.store_id == store_id, Purchase.id == purchase_id
    )
    return db.scalar(stmt)


def count_purchases(
    db: Session, store_id: uuid.UUID, *, status: str | None
) -> int:
    stmt = select(func.count()).select_from(Purchase).where(Purchase.store_id == store_id)
    if status:
        stmt = stmt.where(Purchase.status == status)
    return int(db.scalar(stmt) or 0)


def list_purchases(
    db: Session, store_id: uuid.UUID, *, status: str | None, limit: int, offset: int
) -> list[Purchase]:
    stmt = select(Purchase).where(Purchase.store_id == store_id)
    if status:
        stmt = stmt.where(Purchase.status == status)
    stmt = stmt.order_by(Purchase.created_at.desc(), Purchase.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_supplier(db: Session, store_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier | None:
    stmt = select(Supplier).where(
        Supplier.store_id == store_id, Supplier.id == supplier_id
    )
    return db.scalar(stmt)


def list_items(db: Session, purchase_id: uuid.UUID) -> list[PurchaseItem]:
    stmt = select(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id)
    return list(db.scalars(stmt).all())


def get_item(db: Session, purchase_id: uuid.UUID, item_id: uuid.UUID) -> PurchaseItem | None:
    stmt = select(PurchaseItem).where(
        PurchaseItem.purchase_id == purchase_id, PurchaseItem.id == item_id
    )
    return db.scalar(stmt)
