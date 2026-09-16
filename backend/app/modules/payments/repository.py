"""Payment persistence helpers (no policy here)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commerce import Order
from app.models.payments import Payment


def get_by_idempotency(db: Session, idempotency_key: str) -> Payment | None:
    return db.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )


def get_by_order(db: Session, order_id: uuid.UUID) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.order_id == order_id))


def get_by_provider_ref(db: Session, provider_ref: str) -> Payment | None:
    return db.scalar(
        select(Payment).where(Payment.provider_ref == provider_ref)
    )


def get_owned(
    db: Session, farmer_id: uuid.UUID, payment_id: uuid.UUID
) -> Payment | None:
    """Payment whose order belongs to the farmer (uniform None otherwise)."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        return None
    order = db.get(Order, payment.order_id)
    if order is None or order.farmer_user_id != farmer_id:
        return None
    return payment
