"""Payment endpoints (thin: auth → service → response).

The webhook route is intentionally UNAUTHENTICATED — provider callbacks carry
an HMAC signature, not a farmer token.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.payments import service
from app.modules.payments.schemas import (
    PaymentInitiateCreate,
    PaymentInitiateOut,
    PaymentOut,
    PaymentWebhook,
    PaymentWebhookOut,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "/initiate", response_model=PaymentInitiateOut, status_code=status.HTTP_201_CREATED
)
def initiate_payment(
    payload: PaymentInitiateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentInitiateOut:
    return service.initiate_payment(
        db,
        current_user,
        order_id=payload.order_id,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/webhook", response_model=PaymentWebhookOut)
def payment_webhook(
    payload: PaymentWebhook, db: Session = Depends(get_db)
) -> PaymentWebhookOut:
    return service.handle_webhook(db, payload)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentOut:
    return service.get_payment(db, current_user, payment_id)
