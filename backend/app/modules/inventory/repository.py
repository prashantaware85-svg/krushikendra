"""Inventory persistence (store-scoped reads; no policy here)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.commerce import OrderItem
from app.models.inventory import InventoryItem, StockMovement
from app.models.store import Product, ProductCategory, ProductVariant


def get_item(db: Session, store_id: uuid.UUID, variant_id: uuid.UUID) -> InventoryItem | None:
    stmt = select(InventoryItem).where(
        InventoryItem.store_id == store_id, InventoryItem.variant_id == variant_id
    )
    return db.scalar(stmt)


def get_or_create_item(
    db: Session, store_id: uuid.UUID, variant_id: uuid.UUID
) -> InventoryItem:
    from decimal import Decimal

    item = get_item(db, store_id, variant_id)
    if item is None:
        item = InventoryItem(
            store_id=store_id,
            variant_id=variant_id,
            qty_on_hand=Decimal("0"),
            qty_reserved=Decimal("0"),
            reorder_level=Decimal("0"),
        )
        db.add(item)
        db.flush()
    return item


def list_all(db: Session, store_id: uuid.UUID) -> list[InventoryItem]:
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.store_id == store_id)
        .order_by(InventoryItem.updated_at.desc(), InventoryItem.id.desc())
    )
    return list(db.scalars(stmt).all())


def list_order_items(db: Session, order_id: uuid.UUID) -> list[OrderItem]:
    stmt = select(OrderItem).where(OrderItem.order_id == order_id)
    return list(db.scalars(stmt).all())


def list_sale_movements(
    db: Session, store_id: uuid.UUID, order_id: uuid.UUID
) -> list[StockMovement]:
    stmt = select(StockMovement).where(
        StockMovement.store_id == store_id,
        StockMovement.reference_type == "order_sale",
        StockMovement.reference_id == order_id,
        StockMovement.movement_type == "sale",
    )
    return list(db.scalars(stmt).all())


def first_return_movement(
    db: Session, store_id: uuid.UUID, order_id: uuid.UUID
) -> StockMovement | None:
    stmt = select(StockMovement).where(
        StockMovement.store_id == store_id,
        StockMovement.reference_type == "order_sale",
        StockMovement.reference_id == order_id,
        StockMovement.movement_type == "return_in",
    )
    return db.scalar(stmt)


def list_pos_sale_movements(
    db: Session, store_id: uuid.UUID, bill_id: uuid.UUID
) -> list[StockMovement]:
    """POS ``sale`` movements for one bill (Step 18 counter completion)."""
    stmt = select(StockMovement).where(
        StockMovement.store_id == store_id,
        StockMovement.reference_type == "pos_sale",
        StockMovement.reference_id == bill_id,
        StockMovement.movement_type == "sale",
    )
    return list(db.scalars(stmt).all())


def first_pos_return_movement(
    db: Session, store_id: uuid.UUID, bill_id: uuid.UUID
) -> StockMovement | None:
    """First POS ``return_in`` for one bill (Step 18 cancel idempotency)."""
    stmt = select(StockMovement).where(
        StockMovement.store_id == store_id,
        StockMovement.reference_type == "pos_sale",
        StockMovement.reference_id == bill_id,
        StockMovement.movement_type == "return_in",
    )
    return db.scalar(stmt)


def count_movements(
    db: Session,
    item_id: uuid.UUID,
    *,
    movement_type: str | None,
    since: datetime | None,
    until: datetime | None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(StockMovement)
        .where(StockMovement.inventory_item_id == item_id)
    )
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if since is not None:
        stmt = stmt.where(StockMovement.created_at >= since)
    if until is not None:
        stmt = stmt.where(StockMovement.created_at < until)
    return int(db.scalar(stmt) or 0)


def list_movements(
    db: Session,
    item_id: uuid.UUID,
    *,
    movement_type: str | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> list[StockMovement]:
    stmt = select(StockMovement).where(StockMovement.inventory_item_id == item_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    if since is not None:
        stmt = stmt.where(StockMovement.created_at >= since)
    if until is not None:
        stmt = stmt.where(StockMovement.created_at < until)
    stmt = stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def recent_movements(db: Session, store_id: uuid.UUID, *, limit: int) -> list[StockMovement]:
    stmt = (
        select(StockMovement)
        .where(StockMovement.store_id == store_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def catalogue_map(
    db: Session, variant_ids: set[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """Read-only catalogue enrichment (variant → product/category names)."""
    if not variant_ids:
        return {}
    variants = list(
        db.scalars(select(ProductVariant).where(ProductVariant.id.in_(variant_ids))).all()
    )
    product_ids = {v.product_id for v in variants}
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids))).all()}
        if product_ids
        else {}
    )
    category_ids = {p.category_id for p in products.values() if p.category_id}
    categories = (
        {
            c.id: c
            for c in db.scalars(select(ProductCategory).where(ProductCategory.id.in_(category_ids))).all()
        }
        if category_ids
        else {}
    )
    out: dict[uuid.UUID, dict] = {}
    for variant in variants:
        product = products.get(variant.product_id)
        category = products.get(variant.product_id) and categories.get(product.category_id) if product else None
        out[variant.id] = {
            "variant_name": variant.name,
            "product_id": product.id if product else None,
            "product_name": product.name if product else None,
            "category_id": category.id if category else None,
        }
    return out


def variant_ids_for_product(db: Session, product_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(ProductVariant.id).where(ProductVariant.product_id == product_id)
    return list(db.scalars(stmt).all())


def variant_ids_for_category(db: Session, category_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = (
        select(ProductVariant.id)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(Product.category_id == category_id)
    )
    return list(db.scalars(stmt).all())
