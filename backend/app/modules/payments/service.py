"""Payment policy: mock-first initiate + HMAC webhook, atomic settlement.

STRICT SEPARATION:
- This module only flips ``Order.payment_status``/``payment_ref`` — it NEVER
  creates, edits, or deletes order items.
- The ONLY khata write in the system happens here, on webhook success, inside
  the same transaction that marks the order paid (via ``khata.service`` with
  ``commit=False``). Double webhook delivery replays to a no-op duplicate.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth import User
from app.models.commerce import Order
from app.models.payments import Payment
from app.modules.khata import service as khata_service
from app.modules.payments import providers, repository
from app.modules.payments.schemas import (
    PaymentInitiateOut,
    PaymentOut,
    PaymentWebhook,
    PaymentWebhookOut,
)


def _err(code: str, message: str, status_code: int) -> AppError:
    return AppError(message, code=code, status_code=status_code)


def _owned_order(db: Session, user: User, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.farmer_user_id != user.id:
        raise _err("ORDER_NOT_FOUND", "Order not found.", status.HTTP_404_NOT_FOUND)
    return order


def _mock_redirect(provider_ref: str) -> tuple[str, bool]:
    settings = get_settings()
    approved = settings.payment_mock_approve
    return (
        f"mock://payments/{provider_ref}?approve={'1' if approved else '0'}",
        approved,
    )


def initiate_payment(
    db: Session, user: User, *, order_id: uuid.UUID, idempotency_key: str
) -> PaymentInitiateOut:
    provider = providers.get_provider(get_settings())  # 503 when disabled
    order = _owned_order(db, user, order_id)
    if order.payment_status != "pending":
        raise _err(
            "PAYMENT_ALREADY_PROCESSED",
            f"Order payment is already {order.payment_status}.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Idempotent replay: same key (or same order) returns the existing row.
    existing = repository.get_by_idempotency(db, idempotency_key)
    if existing is None:
        existing = repository.get_by_order(db, order.id)
    if existing is not None:
        redirect_url, approved = _mock_redirect(existing.provider_ref)
        out = PaymentInitiateOut.model_validate(existing)
        out.redirect_url = redirect_url
        out.approved = approved
        return out

    settings = get_settings()
    result = provider.initiate(
        order_id=order.id,
        amount_paise=order.total_paise,
        currency=settings.payment_currency,
        idempotency_key=idempotency_key,
    )
    payment = Payment(
        order_id=order.id,
        provider=provider.name,
        provider_ref=result.provider_ref,
        amount_paise=order.total_paise,
        currency=settings.payment_currency,
        status="initiated",
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with an identical initiate — return the winner.
        db.rollback()
        existing = repository.get_by_order(db, order.id)
        if existing is None:
            raise
        redirect_url, approved = _mock_redirect(existing.provider_ref)
        out = PaymentInitiateOut.model_validate(existing)
        out.redirect_url = redirect_url
        out.approved = approved
        return out
    db.refresh(payment)
    out = PaymentInitiateOut.model_validate(payment)
    out.redirect_url = result.redirect_url
    out.approved = result.approved
    return out


def verify_signature(provider_ref: str, status_value: str, signature: str | None) -> None:
    """HMAC-SHA256 over ``provider_ref.status``. Fail closed: a missing/empty
    secret never accepts (production → 503 PAYMENT_WEBHOOK_NOT_CONFIGURED,
    otherwise → 401 PAYMENT_SIGNATURE_MISSING). The ONLY bypass is unsigned
    mock callbacks when environment != production AND provider == mock AND
    PAYMENT_ALLOW_UNSIGNED_MOCK_WEBHOOK is True."""
    settings = get_settings()
    secret = settings.payment_webhook_secret
    if not secret:
        if (
            not signature
            and settings.environment != "production"
            and settings.payment_provider == "mock"
            and settings.payment_allow_unsigned_mock_webhook
        ):
            return
        if settings.environment == "production":
            raise _err(
                "PAYMENT_WEBHOOK_NOT_CONFIGURED",
                "Webhook secret is not configured.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        raise _err(
            "PAYMENT_SIGNATURE_MISSING",
            "Webhook signature is required.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not signature:
        raise _err(
            "PAYMENT_SIGNATURE_MISSING",
            "Webhook signature is required.",
            status.HTTP_401_UNAUTHORIZED,
        )
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{provider_ref}.{status_value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise _err(
            "PAYMENT_SIGNATURE_INVALID",
            "Webhook signature mismatch.",
            status.HTTP_401_UNAUTHORIZED,
        )


def handle_webhook(db: Session, payload: PaymentWebhook) -> PaymentWebhookOut:
    verify_signature(payload.provider_ref, payload.status, payload.signature)
    payment = repository.get_by_provider_ref(db, payload.provider_ref)
    if payment is None:
        raise _err(
            "PAYMENT_NOT_FOUND", "Payment not found.", status.HTTP_404_NOT_FOUND
        )
    raw = payload.model_dump()

    # Idempotent double-delivery: success replays change nothing.
    if payment.status == "success":
        payment.raw_callback_json = raw
        db.commit()
        order = db.get(Order, payment.order_id)
        return PaymentWebhookOut(
            status=payment.status,
            order_payment_status=order.payment_status if order else "paid",
            duplicate=True,
        )

    if payload.status == "failed":
        try:
            payment.status = "failed"
            payment.raw_callback_json = raw
            order = db.get(Order, payment.order_id)
            # Never regress a paid order on a late failure callback.
            if order is not None and order.payment_status == "pending":
                order.payment_status = "failed"
            db.commit()
        except Exception:
            db.rollback()
            raise
        order = db.get(Order, payment.order_id)
        return PaymentWebhookOut(
            status="failed",
            order_payment_status=order.payment_status if order else "failed",
        )

    # Success: mark paid + append the single khata payment entry, atomically.
    try:
        payment.status = "success"
        payment.raw_callback_json = raw
        order = db.get(Order, payment.order_id)
        if order is None:
            raise _err(
                "ORDER_NOT_FOUND", "Order not found.", status.HTTP_404_NOT_FOUND
            )
        order.payment_status = "paid"
        order.payment_ref = payment.provider_ref
        khata_entry_id: uuid.UUID | None = None
        if get_settings().khata_enabled:
            entry = khata_service.append_entry(
                db,
                farmer_id=order.farmer_user_id,
                entry_type="payment",
                amount_paise=payment.amount_paise,
                order_id=order.id,
                note=(
                    f"Payment {payment.provider_ref} "
                    f"for order {order.order_number or order.id}"
                ),
                commit=False,
            )
            khata_entry_id = entry.id
        db.commit()  # single commit: paid status + khata entry or neither
    except Exception:
        db.rollback()
        raise
    if khata_entry_id is not None:
        db.refresh(payment)
    return PaymentWebhookOut(
        status="success",
        order_payment_status="paid",
        khata_entry_id=khata_entry_id,
    )


def get_payment(db: Session, user: User, payment_id: uuid.UUID) -> PaymentOut:
    payment = repository.get_owned(db, user.id, payment_id)
    if payment is None:
        raise _err(
            "PAYMENT_NOT_FOUND", "Payment not found.", status.HTTP_404_NOT_FOUND
        )
    return PaymentOut.model_validate(payment)
