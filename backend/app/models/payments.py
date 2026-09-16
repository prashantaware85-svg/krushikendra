"""Payment models (Step 15).

Mock-first: every row records which provider handled it (default ``mock``).
State is driven by initiate → webhook/callback only — commerce never writes
here, and success/failure is never faked at checkout time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

PAYMENT_STATUSES = ("pending", "initiated", "success", "failed")


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One payment attempt per order (``order_id`` unique)."""

    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), default="mock", nullable=False)
    provider_ref: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False
    )
    raw_callback_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
