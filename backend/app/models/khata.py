"""Khata ledger models (Step 15).

Immutable entries only — no edit/delete. There is NO stored mutable balance:
the farmer balance is always computed on read as
``sum(credits + payments) − sum(debits)`` (``balance_after_paise`` is a
per-row audit snapshot, not a source of truth).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

KHATA_ENTRY_TYPES = ("debit", "credit", "payment")


class KhataEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single immutable ledger line, farmer-scoped."""

    __tablename__ = "khata_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('debit', 'credit', 'payment')",
            name="ck_khata_entries_entry_type",
        ),
        CheckConstraint("amount_paise > 0", name="ck_khata_entries_amount_positive"),
    )

    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
