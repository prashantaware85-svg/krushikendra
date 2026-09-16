"""Commerce persistence helpers (farmer-scoped; no policy here)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.commerce import (
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderCounter,
    OrderItem,
    OrderStatusHistory,
)
from app.models.store import Product, ProductVariant


# ── Cart ──────────────────────────────────────────────────────────────
def get_cart(db: Session, farmer_id: uuid.UUID) -> Cart | None:
    return db.scalar(select(Cart).where(Cart.farmer_user_id == farmer_id))


def get_or_create_cart(db: Session, farmer_id: uuid.UUID) -> Cart:
    cart = get_cart(db, farmer_id)
    if cart is None:
        cart = Cart(farmer_user_id=farmer_id)
        db.add(cart)
        db.flush()
    return cart


def list_cart_items(db: Session, cart_id: uuid.UUID) -> list[CartItem]:
    stmt = select(CartItem).where(CartItem.cart_id == cart_id)
    return list(db.scalars(stmt).all())


def get_cart_item(db: Session, item_id: uuid.UUID) -> CartItem | None:
    return db.get(CartItem, item_id)


def get_variant(db: Session, variant_id: uuid.UUID) -> ProductVariant | None:
    return db.get(ProductVariant, variant_id)


def get_product(db: Session, product_id: uuid.UUID) -> Product | None:
    return db.get(Product, product_id)


def count_distinct_items(db: Session, cart_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(CartItem)
        .where(CartItem.cart_id == cart_id)
    )
    return int(db.scalar(stmt) or 0)


def delete_cart_items(db: Session, cart_id: uuid.UUID) -> None:
    db.execute(delete(CartItem).where(CartItem.cart_id == cart_id))


# ── Addresses ─────────────────────────────────────────────────────────
def list_addresses(db: Session, farmer_id: uuid.UUID) -> list[DeliveryAddress]:
    stmt = (
        select(DeliveryAddress)
        .where(DeliveryAddress.farmer_user_id == farmer_id)
        .order_by(DeliveryAddress.created_at)
    )
    return list(db.scalars(stmt).all())


def get_address(
    db: Session, farmer_id: uuid.UUID, address_id: uuid.UUID
) -> DeliveryAddress | None:
    address = db.get(DeliveryAddress, address_id)
    if address is None or address.farmer_user_id != farmer_id:
        return None
    return address


def newest_other_address(
    db: Session, farmer_id: uuid.UUID, exclude_id: uuid.UUID
) -> DeliveryAddress | None:
    stmt = (
        select(DeliveryAddress)
        .where(
            DeliveryAddress.farmer_user_id == farmer_id,
            DeliveryAddress.id != exclude_id,
        )
        .order_by(DeliveryAddress.created_at.desc())
    )
    return db.scalar(stmt)


# ── Orders ────────────────────────────────────────────────────────────
def list_orders(db: Session, farmer_id: uuid.UUID) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.farmer_user_id == farmer_id)
        .order_by(Order.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_order(
    db: Session, farmer_id: uuid.UUID, order_id: uuid.UUID
) -> Order | None:
    order = db.get(Order, order_id)
    if order is None or order.farmer_user_id != farmer_id:
        return None
    return order


def list_order_items(db: Session, order_id: uuid.UUID) -> list[OrderItem]:
    stmt = select(OrderItem).where(OrderItem.order_id == order_id)
    return list(db.scalars(stmt).all())


def list_history(db: Session, order_id: uuid.UUID) -> list[OrderStatusHistory]:
    stmt = (
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.changed_at)
    )
    return list(db.scalars(stmt).all())


def next_order_sequence(db: Session) -> int:
    """Allocate the next human-readable order number (concurrency-safe)."""
    counter = OrderCounter()
    db.add(counter)
    db.flush()
    return int(counter.id)
