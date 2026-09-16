"""Inventory models (Step 16).

Suppliers → purchases (+ items) → per-variant stock levels + immutable
stock-movement audit trail. No GST computation, no coupons, no valuation,
no batch traceability (explicitly out of scope for this step).

Money convention: all money fields are integer paise (``*_paise``), NOT
``Numeric``. Steps 13–15 use paise ints throughout (see
``Product.price_paise``, ``Order.total_paise``, ``Payment.amount_paise``,
``KhataEntry.amount_paise``) so integer arithmetic avoids float rounding
entirely; quantities (kgs/litres/units) use ``Numeric(14, 3)`` because they
are fractional by nature.

Coupling convention: ``variant_id`` / ``created_by`` / ``store_id`` are
plain ``Uuid`` columns validated service-side — no hard FKs to
``product_variants`` / ``users`` / stores. This mirrors the vision/soil
pattern (``CropImageAnalysis.farmer_user_id`` etc. are plain UUIDs) and
avoids cross-agent coupling while keeping index support for lookups.

Single-store default: there is NO ``stores`` table (out of scope).
``store_id`` on every row is filled from ``DEFAULT_STORE_ID`` below;
multi-store support is future work (replace the constant with a real FK).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: Single-store default. All ``store_id`` columns are filled from this until
#: a real multi-store model lands (then this becomes a FK to a stores table).
DEFAULT_STORE_ID: uuid.UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")

STOCK_MOVEMENT_TYPES = (
    "purchase",
    "sale",
    "adjustment_in",
    "adjustment_out",
    "return_in",
    "damaged_out",
    "expired_out",
    "transfer_in",
    "transfer_out",
    "opening_stock",
)

_MOVEMENT_TYPE_LIST = ", ".join(f"'{t}'" for t in STOCK_MOVEMENT_TYPES)


class Supplier(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Purchase source. ``gstin`` stored only — never validated here."""

    __tablename__ = "suppliers"

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Purchase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Supplier purchase header. Money in integer paise (see module docstring)."""

    __tablename__ = "purchases"
    __table_args__ = (
        UniqueConstraint("store_id", "purchase_number", name="uq_purchases_store_id_purchase_number"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    purchase_number: Mapped[str] = mapped_column(String(40), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    other_charges_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # Plain UUID (no hard FK to users.id) — mirrors vision/soil pattern to
    # avoid cross-agent coupling; validated service-side.
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)


class PurchaseItem(Base, UUIDPrimaryKeyMixin):
    """One variant line on a purchase. Money in integer paise."""

    __tablename__ = "purchase_items"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("purchases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Plain UUID (no hard FK to product_variants) — validated service-side.
    # NOT NULL: a purchase line must always name a variant.
    variant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(Integer, nullable=False)


class InventoryItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-variant stock level. One row per (store, variant)."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("store_id", "variant_id", name="uq_inventory_items_store_id_variant_id"),
        CheckConstraint("qty_on_hand >= 0", name="ck_inventory_items_qty_on_hand_nonneg"),
        CheckConstraint("qty_reserved >= 0", name="ck_inventory_items_qty_reserved_nonneg"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    # Plain UUID (no hard FK to product_variants) — validated service-side.
    variant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    qty_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    qty_reserved: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    reorder_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StockMovement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable stock-movement audit line (mirror khata immutable-ledger pattern).

    No edit/delete — corrections are new offsetting rows. ``qty`` is always
    positive; direction comes from ``movement_type``. ``qty_before`` /
    ``qty_after`` are audit snapshots; current stock is derived from
    ``InventoryItem`` on read.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        # One movement per (reference, type, inventory line): multi-line
        # documents (purchase with N variants, order with N lines) write one
        # row per line; repeats of the same line are rejected (idempotency).
        UniqueConstraint(
            "reference_type",
            "reference_id",
            "movement_type",
            "inventory_item_id",
            name="uq_stock_move_ref_type",
        ),
        CheckConstraint(
            f"movement_type IN ({_MOVEMENT_TYPE_LIST})",
            name="ck_stock_movements_movement_type",
        ),
        CheckConstraint("qty > 0", name="ck_stock_movements_qty_positive"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Plain UUID (no hard FK to product_variants) — validated service-side.
    variant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    qty_before: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    qty_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(
        String(40), index=True, nullable=True
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, index=True, nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain UUID (no hard FK to users.id) — mirrors vision/soil pattern.
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
