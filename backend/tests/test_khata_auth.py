"""Khata creation-authorization audit tests (Step 15 contracts).

Scope: no staff/admin roles exist — authorization here means:
- khata router is GET-only (no POST/PUT/PATCH/DELETE creates entries),
- ledger reads are farmer-scoped,
- the ONLY khata writer is payments.handle_webhook (entry_type payment),
  gated by HMAC webhook auth,
- no DELETE route hard-deletes payments/khata/orders (cancel/status only).

All webhook success posts in this file use valid HMAC signatures with an
explicit secret (never relies on unsigned acceptance).
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

SECRET = "khata-auth-test-secret"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (khata auth audit test)")
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
    with TestingSession() as db:
        category = ProductCategory(name=f"Seeds-{uuid.uuid4().hex[:6]}")
        db.add(category)
        db.flush()
        product = Product(
            name=f"Cotton-{uuid.uuid4().hex[:6]}", category_id=category.id, is_active=True
        )
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


def sign(provider_ref: str, status_value: str, secret: str = SECRET) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{provider_ref}.{status_value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def initiate(client: TestClient, headers: dict, order_id: str, key: str) -> dict:
    response = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "idempotency_key": key},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def khata_entries(client: TestClient, headers: dict) -> list:
    response = client.get("/api/v1/khata/entries", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["entries"]


# ── 1. No mutating route on /khata/* ──────────────────────────────────
def test_khata_mutating_methods_not_allowed(client: TestClient):
    _, headers = make_farmer("9400000001")
    fake_id = str(uuid.uuid4())
    assert client.post(
        "/api/v1/khata/entries", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.post(
        "/api/v1/khata/summary", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.put(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.patch(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.delete(
        f"/api/v1/khata/entries/{fake_id}", headers=headers
    ).status_code in (404, 405)
    assert client.delete("/api/v1/khata/summary", headers=headers).status_code in (
        404,
        405,
    )
    # Unauthenticated mutating attempts must not create either (still 401/404/405).
    assert client.post("/api/v1/khata/entries", json={}).status_code in (401, 404, 405)


def test_khata_reads_require_auth(client: TestClient):
    assert client.get("/api/v1/khata/summary").status_code == 401
    assert client.get("/api/v1/khata/entries").status_code == 401


# ── 2. Cross-farmer ledger invisible ──────────────────────────────────
def test_cross_farmer_ledger_invisible(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = SECRET
    try:
        _, headers_a = make_farmer("9400000002")
        _, headers_b = make_farmer("9400000003")
        order = checkout_order(client, headers_a)
        payment = initiate(client, headers_a, order["id"], "khata-auth-key-01")
        ok = client.post(
            "/api/v1/payments/webhook",
            json={
                "provider_ref": payment["provider_ref"],
                "status": "success",
                "signature": sign(payment["provider_ref"], "success"),
            },
        )
        assert ok.status_code == 200, ok.text
        assert len(khata_entries(client, headers_a)) == 1
        # Stranger sees an empty ledger, never farmer A's rows.
        assert khata_entries(client, headers_b) == []
        other = client.get("/api/v1/khata/summary", headers=headers_b).json()
        assert other["total_payments_paise"] == 0
        assert other["outstanding_paise"] == 0
        own = client.get("/api/v1/khata/summary", headers=headers_a).json()
        assert own["total_payments_paise"] == order["total_paise"]
    finally:
        settings.payment_webhook_secret = old_secret


# ── 3. Webhook unsigned/invalid rejected (fail-closed with secret) ────
def test_webhook_unsigned_and_invalid_rejected(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = SECRET
    try:
        _, headers = make_farmer("9400000004")
        order = checkout_order(client, headers)
        payment = initiate(client, headers, order["id"], "khata-auth-key-02")
        ref = payment["provider_ref"]

        missing = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success"},
        )
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "PAYMENT_SIGNATURE_MISSING"

        wrong = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success", "signature": "wrong"},
        )
        assert wrong.status_code == 401
        assert wrong.json()["error"]["code"] == "PAYMENT_SIGNATURE_INVALID"

        # Rejected callbacks write zero khata rows and leave order pending.
        assert khata_entries(client, headers) == []
        fetched = client.get(
            f"/api/v1/store/orders/{order['id']}", headers=headers
        ).json()
        assert fetched["payment_status"] == "pending"

        # Valid signed callback still settles exactly one payment entry.
        ok = client.post(
            "/api/v1/payments/webhook",
            json={
                "provider_ref": ref,
                "status": "success",
                "signature": sign(ref, "success"),
            },
        )
        assert ok.status_code == 200, ok.text
        entries = khata_entries(client, headers)
        assert len(entries) == 1
        assert entries[0]["entry_type"] == "payment"
    finally:
        settings.payment_webhook_secret = old_secret


# ── 4. No DELETE route deletes a payment/khata row ────────────────────
def test_no_delete_route_removes_payment_or_khata(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = SECRET
    try:
        _, headers = make_farmer("9400000005")
        order = checkout_order(client, headers)
        payment = initiate(client, headers, order["id"], "khata-auth-key-03")
        ok = client.post(
            "/api/v1/payments/webhook",
            json={
                "provider_ref": payment["provider_ref"],
                "status": "success",
                "signature": sign(payment["provider_ref"], "success"),
            },
        )
        assert ok.status_code == 200, ok.text
        assert len(khata_entries(client, headers)) == 1

        # Every plausible DELETE is not-a-route or wrong-method, never a delete.
        assert client.delete(
            f"/api/v1/payments/{payment['id']}", headers=headers
        ).status_code in (404, 405)
        assert client.delete("/api/v1/payments/webhook").status_code in (404, 405)
        assert client.delete(
            f"/api/v1/store/orders/{order['id']}", headers=headers
        ).status_code in (404, 405)
        fake_id = str(uuid.uuid4())
        assert client.delete(
            f"/api/v1/khata/entries/{fake_id}", headers=headers
        ).status_code in (404, 405)
        assert client.delete(f"/api/v1/payments/{fake_id}", headers=headers).status_code in (
            404,
            405,
        )

        # Rows survive: payment readable, khata entry intact, order only cancellable.
        own = client.get(f"/api/v1/payments/{payment['id']}", headers=headers)
        assert own.status_code == 200
        assert len(khata_entries(client, headers)) == 1
        fetched = client.get(
            f"/api/v1/store/orders/{order['id']}", headers=headers
        ).json()
        assert fetched["payment_status"] == "paid"
    finally:
        settings.payment_webhook_secret = old_secret
