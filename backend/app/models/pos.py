"""Counter billing (POS) models (Step 18).

Counter-sale bills for in-store staff operation. Money convention: all
money fields are integer paise (``*_paise``), NEVER float — integer
arithmetic avoids rounding entirely (mirrors Steps 13–16:
``Product.price_paise``, ``Order.total_paise``, ``KhataEntry.amount_paise``).
Quantities (kgs/litres/units) use ``Numeric(14, 3)`` because they are
fractional by nature.

Coupling convention: ``customer_id`` / ``variant_id`` / ``sold_by`` /
``cancelled_by`` are plain ``Uuid`` columns validated service-side — no
hard FKs to ``users.id`` / ``product_variants.id``. This mirrors the
inventory/vision pattern and avoids cross-domain coupling. Single store:
``store_id`` is filled from ``DEFAULT_STORE_ID`` (imported from the
inventory model to avoid drift); there is NO ``stores`` table.

Catalogue has NO SKU/barcode fields (Step 13): POS product search covers
product name + variant name only (ILIKE); no SKU/barcode columns are added
here by design.

Users have NO cross-store ``store_id`` (single store): POS customer
validation checks existence + active only, documented in the service.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.inventory import DEFAULT_STORE_ID

#: Counter-sale lifecycle: draft (no stock effect) → completed (stock
#: decremented) or cancelled (draft: no effect; completed: stock restored).
POS_SALE_STATUSES: tuple[str, ...] = ("draft", "completed", "cancelled")

#: Payment outcome on a bill.
POS_PAYMENT_STATUSES: tuple[str, ...] = ("pending", "paid", "partial", "credit")

#: Accepted counter payment modes (no gateway in this step).
POS_PAYMENT_MODES: tuple[str, ...] = ("cash", "upi", "card", "credit")

_SALE_LIST = ", ".join(f"'{s}'" for s in POS_SALE_STATUSES)
_PAYMENT_STATUS_LIST = ", ".join(f"'{s}'" for s in POS_PAYMENT_STATUSES)
_PAYMENT_MODE_LIST = ", ".join(f"'{m}'" for m in POS_PAYMENT_MODES)


class PosBill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One counter bill. Draft rows hold intent only; completion decrements
    stock and (for credit/partial) appends Khata debits."""

    __tablename__ = "pos_bills"
    __table_args__ = (
        UniqueConstraint("store_id", "bill_number", name="uq_pos_bills_store_bill"),
        CheckConstraint(
            f"sale_status IN ({_SALE_LIST})", name="ck_pos_bills_sale_status"
        ),
        CheckConstraint(
            f"payment_status IN ({_PAYMENT_STATUS_LIST})",
            name="ck_pos_bills_payment_status",
        ),
        CheckConstraint(
            f"(payment_mode IS NULL OR payment_mode IN ({_PAYMENT_MODE_LIST}))",
            name="ck_pos_bills_payment_mode",
        ),
        Index("ix_pos_bills_store_created", "store_id", "created_at"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, index=True, nullable=False, default=lambda: DEFAULT_STORE_ID
    )
    bill_number: Mapped[str] = mapped_column(String(40), nullable=False)
    # Plain UUID (= users.id), validated service-side; nullable = walk-in.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, index=True, nullable=True
    )
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    other_charges_paise: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    sale_status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_received_paise: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    amount_paid_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    balance_due_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_reference: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain UUID (staff user id), validated service-side.
    sold_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class PosBillItem(Base, UUIDPrimaryKeyMixin):
    """One priced line on a bill. Snapshot names/prices at creation;
    immutable after create (no draft-edit endpoints; the frontend cart is
    client-side)."""

    __tablename__ = "pos_bill_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_pos_bill_items_qty_positive"),
    )

    pos_bill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pos_bills.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Plain UUID (no hard FK to product_variants) — validated service-side.
    variant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(Integer, nullable=False)


class PosBillCounter(Base):
    """Human-readable bill sequence. One row per bill; ``id`` feeds
    ``PosBill.bill_number`` (``KSK-{year}-{seq:06d}``). Mirrors OrderCounter."""

    __tablename__ = "pos_bill_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
