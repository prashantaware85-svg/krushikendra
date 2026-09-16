"""Payments (mock-first) + Khata ledger tests (SQLite, minimal app).

Covers: mock initiate → success webhook → single khata entry; idempotent
double-delivery; checkout writes zero khata rows; outstanding math; strict
commerce/payments separation; HMAC webhook auth; khata immutability.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.auth import User
from app.models.commerce import (
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderCounter,
    OrderItem,
    OrderStatusHistory,
)
from app.models.khata import KhataEntry
from app.models.payments import Payment
from app.models.store import Product, ProductCategory, ProductVariant
from app.modules.commerce.router import router as commerce_router
from app.modules.khata import service as khata_service
from app.modules.khata.router import router as khata_router
from app.modules.payments.router import router as payments_router
from app.modules.store.router import router as store_router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

TABLES = [
    User.__table__,
    ProductCategory.__table__,
    Product.__table__,
    ProductVariant.__table__,
    Cart.__table__,
    CartItem.__table__,
    DeliveryAddress.__table__,
    Order.__table__,
    OrderItem.__table__,
    OrderStatusHistory.__table__,
    OrderCounter.__table__,
    Payment.__table__,
    KhataEntry.__table__,
]

ADDRESS = {
    "label": "Home",
    "line1": "123 Farm Road",
    "city": "Nashik",
    "state": "Maharashtra",
    "pincode": "422001",
    "phone": "9876543210",
}


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (payments/khata test)")
    register_exception_handlers(app)
    app.include_router(store_router, prefix="/api/v1")
    app.include_router(commerce_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(khata_router, prefix="/api/v1")
    return app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=TABLES)
    Base.metadata.create_all(bind=engine, tables=TABLES)
    app = build_test_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_farmer(mobile: str) -> tuple[uuid.UUID, dict]:
    from app.modules.auth.security import create_access_token

    with TestingSession() as db:
        user = User(mobile_number=mobile, is_verified=True, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(str(user.id), get_settings())
        return user.id, {"Authorization": f"Bearer {token}"}


def checkout_order(client: TestClient, headers: dict, *, price: int = 25000) -> dict:
    """Seed catalogue → cart → address → checkout. Returns the order JSON."""
    with TestingSession() as db:
        category = ProductCategory(name="Seeds")
        db.add(category)
        db.flush()
        product = Product(name="Cotton Seeds", category_id=category.id, is_active=True)
        db.add(product)
        db.flush()
        variant = ProductVariant(
            product_id=product.id, name="1 kg", price_paise=price, stock_qty=10
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)
        variant_id = str(variant.id)
    assert (
        client.post(
            "/api/v1/store/cart/items",
            json={"variant_id": variant_id, "qty": 1},
            headers=headers,
        ).status_code
        == 201
    )
    address = client.post(
        "/api/v1/store/addresses", json=ADDRESS, headers=headers
    ).json()
    response = client.post(
        "/api/v1/store/checkout",
        json={"address_id": address["id"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def khata_entries(client: TestClient, headers: dict) -> list:
    response = client.get("/api/v1/khata/entries", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["entries"]


_TEST_WEBHOOK_SECRET = "test-webhook-secret"


def _sign(ref: str, status_value: str, secret: str = _TEST_WEBHOOK_SECRET) -> str:
    return hmac.new(
        secret.encode(), f"{ref}.{status_value}".encode(), hashlib.sha256
    ).hexdigest()


def _signed_webhook(ref: str, status_value: str, **extra) -> dict:
    get_settings().payment_webhook_secret = _TEST_WEBHOOK_SECRET
    payload = {
        "provider_ref": ref,
        "status": status_value,
        "signature": _sign(ref, status_value),
    }
    payload.update(extra)
    return payload


# ── Separation: checkout writes zero khata rows ───────────────────────
def test_checkout_creates_zero_khata_entries(client: TestClient):
    _, headers = make_farmer("9100000001")
    order = checkout_order(client, headers)
    assert order["payment_status"] == "pending"

    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["total_debits_paise"] == 0
    assert summary["total_credits_paise"] == 0
    assert summary["total_payments_paise"] == 0
    assert summary["outstanding_paise"] == 0
    assert khata_entries(client, headers) == []


# ── Mock initiate → success webhook (idempotent) ──────────────────────
def test_mock_initiate_success_webhook_idempotent(client: TestClient):
    farmer_id, headers = make_farmer("9100000002")
    order = checkout_order(client, headers)
    items_before = order["items"]

    response = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "key-000001"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    payment = response.json()
    assert payment["provider"] == "mock"
    assert payment["provider_ref"].startswith("mock_")
    assert payment["redirect_url"].startswith("mock://payments/")
    assert payment["status"] == "initiated"
    assert payment["amount_paise"] == order["total_paise"]

    webhook = _signed_webhook(payment["provider_ref"], "success")
    first = client.post("/api/v1/payments/webhook", json=webhook)
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    assert first.json()["khata_entry_id"] is not None

    fetched = client.get(f"/api/v1/store/orders/{order['id']}", headers=headers).json()
    assert fetched["payment_status"] == "paid"
    assert fetched["payment_ref"] == payment["provider_ref"]
    # Payments never change order items.
    assert fetched["items"] == items_before

    entries = khata_entries(client, headers)
    assert len(entries) == 1
    assert entries[0]["entry_type"] == "payment"
    assert entries[0]["amount_paise"] == order["total_paise"]
    assert entries[0]["order_id"] == order["id"]

    # Double delivery: same success, no duplicate khata row.
    second = client.post("/api/v1/payments/webhook", json=webhook)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert len(khata_entries(client, headers)) == 1

    # Re-initiating a paid order is rejected.
    response = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "key-000002"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PAYMENT_ALREADY_PROCESSED"


def test_initiate_idempotent_same_key(client: TestClient):
    _, headers = make_farmer("9100000003")
    order = checkout_order(client, headers)

    first = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "same-key-1"},
        headers=headers,
    ).json()
    second = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "same-key-1"},
        headers=headers,
    ).json()
    assert first["id"] == second["id"]
    assert first["provider_ref"] == second["provider_ref"]


def test_failed_webhook_marks_failed_no_khata(client: TestClient):
    _, headers = make_farmer("9100000004")
    order = checkout_order(client, headers)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "fail-key-1"},
        headers=headers,
    ).json()

    response = client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(payment["provider_ref"], "failed"),
    )
    assert response.status_code == 200, response.text
    fetched = client.get(f"/api/v1/store/orders/{order['id']}", headers=headers).json()
    assert fetched["payment_status"] == "failed"
    assert khata_entries(client, headers) == []


# ── Outstanding math ──────────────────────────────────────────────────
def test_outstanding_math(client: TestClient):
    farmer_id, headers = make_farmer("9100000005")

    with TestingSession() as db:
        khata_service.record_debit(
            db, farmer_id=farmer_id, amount_paise=5000, note="Test amount owed"
        )
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["total_debits_paise"] == 5000
    assert summary["outstanding_paise"] == 5000
    assert summary["over_limit"] is True  # default KHATA_CREDIT_LIMIT=0

    order = checkout_order(client, headers, price=2000)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "math-key-1"},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(payment["provider_ref"], "success"),
    )
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["total_payments_paise"] == 2000
    assert summary["outstanding_paise"] == 3000  # 5000 owed − 2000 paid

    entries = khata_entries(client, headers)
    assert [e["entry_type"] for e in entries] == ["payment", "debit"]  # newest first


# ── Webhook HMAC ──────────────────────────────────────────────────────
def test_webhook_signature_enforced(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = "s3cr3t"
    try:
        _, headers = make_farmer("9100000006")
        order = checkout_order(client, headers)
        payment = client.post(
            "/api/v1/payments/initiate",
            json={"order_id": order["id"], "idempotency_key": "sig-key-1"},
            headers=headers,
        ).json()
        ref = payment["provider_ref"]

        response = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success"},
        )
        assert response.status_code == 401

        response = client.post(
            "/api/v1/payments/webhook",
            json={
                "provider_ref": ref,
                "status": "success",
                "signature": "wrong",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "PAYMENT_SIGNATURE_INVALID"

        good = hmac.new(
            b"s3cr3t", f"{ref}.success".encode(), hashlib.sha256
        ).hexdigest()
        response = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success", "signature": good},
        )
        assert response.status_code == 200, response.text
    finally:
        settings.payment_webhook_secret = old_secret


# ── Khata immutability ────────────────────────────────────────────────
def test_khata_has_no_write_endpoints(client: TestClient):
    _, headers = make_farmer("9100000007")
    assert client.post("/api/v1/khata/entries", json={}, headers=headers).status_code in (
        404,
        405,
    )
    fake_id = str(uuid.uuid4())
    assert client.put(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.delete(
        f"/api/v1/khata/entries/{fake_id}", headers=headers
    ).status_code in (404, 405)


def test_khata_requires_auth_and_farmer_scoping(client: TestClient):
    farmer_a, headers_a = make_farmer("9100000008")
    _, headers_b = make_farmer("9100000009")

    assert client.get("/api/v1/khata/summary").status_code == 401

    with TestingSession() as db:
        khata_service.record_debit(
            db, farmer_id=farmer_a, amount_paise=1500, note="A owes"
        )
    assert client.get("/api/v1/khata/summary", headers=headers_a).json()[
        "outstanding_paise"
    ] == 1500
    other = client.get("/api/v1/khata/summary", headers=headers_b).json()
    assert other["outstanding_paise"] == 0
    assert khata_entries(client, headers_b) == []
