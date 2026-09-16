"""Cart / orders / delivery models (Step 14 rebuild).

Checkout creates orders with *snapshotted* unit prices and
``payment_status="pending"``. Payment processing (Step 15) only flips the
status columns via the payments module — it never edits items here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ORDER_STATUSES = ("pending", "confirmed", "shipped", "delivered", "cancelled")
ORDER_PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded")

#: Farmer-initiated forward transitions (admin-driven; no farmer route).
ORDER_MACHINE: dict[str, tuple[str, ...]] = {
    "pending": ("confirmed", "cancelled"),
    "confirmed": ("shipped", "cancelled"),
    "shipped": ("delivered",),
    "delivered": (),
    "cancelled": (),
}


class Cart(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Exactly one cart row per farmer (``farmer_user_id`` unique)."""

    __tablename__ = "carts"

    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )


class CartItem(Base, UUIDPrimaryKeyMixin):
    """One variant line in a cart. Same variant merges (unique pair)."""

    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("carts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)


class DeliveryAddress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Farmer-owned delivery address. Exactly one default per farmer."""

    __tablename__ = "delivery_addresses"

    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Snapshotted order. ``order_number`` is the human-readable sequence."""

    __tablename__ = "orders"

    order_number: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("delivery_addresses.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    payment_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)


class OrderItem(Base, UUIDPrimaryKeyMixin):
    """Price snapshot line. ``variant_id`` NULLABLE so catalogue deletions
    never rewrite history (reads never join the catalogue)."""

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)


class OrderStatusHistory(Base, UUIDPrimaryKeyMixin):
    """Append-only transition log (one row per change, incl. creation)."""

    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrderCounter(Base):
    """Human-readable order sequence. One row per order; ``id`` feeds
    ``Order.order_number`` (``KS-000001`` …)."""

    __tablename__ = "order_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
