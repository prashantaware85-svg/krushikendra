"""Payments security tests: auth, webhook HMAC, idempotency, tamper (SQLite).

Follows tests/test_payments_khata.py exactly: a minimal FastAPI app mounting
ONLY the store + commerce + payments + khata routers, scoped TABLES, farmers
minted via real DB rows + ``create_access_token``.
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


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (payments security test)")
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
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": variant_id, "qty": 1},
        headers=headers,
    ).status_code == 201
    address = client.post(
        "/api/v1/store/addresses", json=ADDRESS, headers=headers
    ).json()
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


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


def test_initiate_and_payment_read_require_auth(client: TestClient):
    _, headers = make_farmer("9300000001")
    order = checkout_order(client, headers)
    assert client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "no-auth-key-1"},
    ).status_code == 401
    payment = initiate(client, headers, order["id"], "auth-key-0001")
    assert client.get(f"/api/v1/payments/{payment['id']}").status_code == 401
    assert client.get("/api/v1/khata/summary").status_code == 401
    assert client.get("/api/v1/khata/entries").status_code == 401


def test_webhook_missing_and_bad_signature_401(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = "s3cr3t"
    try:
        _, headers = make_farmer("9300000002")
        order = checkout_order(client, headers)
        payment = initiate(client, headers, order["id"], "sig-key-0001")
        ref = payment["provider_ref"]
        missing = client.post(
            "/api/v1/payments/webhook", json={"provider_ref": ref, "status": "success"}
        )
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "PAYMENT_SIGNATURE_MISSING"
        wrong = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success", "signature": "wrong"},
        )
        assert wrong.status_code == 401
        assert wrong.json()["error"]["code"] == "PAYMENT_SIGNATURE_INVALID"
        good = hmac.new(
            b"s3cr3t", f"{ref}.success".encode(), hashlib.sha256
        ).hexdigest()
        ok = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success", "signature": good},
        )
        assert ok.status_code == 200, ok.text
    finally:
        settings.payment_webhook_secret = old_secret


def test_webhook_unknown_ref_404_and_bad_status_422(client: TestClient):
    settings = get_settings()
    old_secret = settings.payment_webhook_secret
    settings.payment_webhook_secret = "s3cr3t"
    try:
        ref = "mock_unknown_ref_xyz"
        good = hmac.new(
            b"s3cr3t", f"{ref}.success".encode(), hashlib.sha256
        ).hexdigest()
        unknown = client.post(
            "/api/v1/payments/webhook",
            json={"provider_ref": ref, "status": "success", "signature": good},
        )
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == "PAYMENT_NOT_FOUND"
    finally:
        settings.payment_webhook_secret = old_secret
    _, headers = make_farmer("9300000003")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "badstatus-01")
    get_settings().payment_webhook_secret = _TEST_WEBHOOK_SECRET
    invalid = client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(payment["provider_ref"], "pending"),
    )
    assert invalid.status_code == 422


def test_double_success_webhook_single_khata_entry(client: TestClient):
    _, headers = make_farmer("9300000004")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "double-key-01")
    webhook = _signed_webhook(payment["provider_ref"], "success")
    first = client.post("/api/v1/payments/webhook", json=webhook)
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    assert first.json()["khata_entry_id"] is not None
    second = client.post("/api/v1/payments/webhook", json=webhook)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    entries = khata_entries(client, headers)
    assert len(entries) == 1
    assert entries[0]["amount_paise"] == order["total_paise"]
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["total_payments_paise"] == order["total_paise"]
    assert summary["outstanding_paise"] == -order["total_paise"] or summary["outstanding_paise"] <= 0


def test_failed_webhook_writes_no_khata_and_marks_failed(client: TestClient):
    _, headers = make_farmer("9300000005")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "fail-key-0001")
    response = client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(payment["provider_ref"], "failed"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["khata_entry_id"] is None
    fetched = client.get(f"/api/v1/store/orders/{order['id']}", headers=headers).json()
    assert fetched["payment_status"] == "failed"
    assert khata_entries(client, headers) == []
    assert client.get("/api/v1/khata/summary", headers=headers).json()[
        "total_payments_paise"
    ] == 0


def test_webhook_amount_tamper_ignored_server_total_wins(client: TestClient):
    _, headers = make_farmer("9300000006")
    order = checkout_order(client, headers, price=20000)
    payment = initiate(client, headers, order["id"], "tamper-key-01")
    assert payment["amount_paise"] == order["total_paise"] == 20000
    response = client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(
            payment["provider_ref"], "success", amount_paise=1
        ),
    )
    assert response.status_code == 200, response.text
    entries = khata_entries(client, headers)
    assert len(entries) == 1
    assert entries[0]["amount_paise"] == 20000  # order total, not the tampered 1


def test_cross_farmer_payment_isolation(client: TestClient):
    _, headers_a = make_farmer("9300000007")
    _, headers_b = make_farmer("9300000008")
    order = checkout_order(client, headers_a)
    stranger_initiate = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "stranger-k1"},
        headers=headers_b,
    )
    assert stranger_initiate.status_code == 404
    assert stranger_initiate.json()["error"]["code"] == "ORDER_NOT_FOUND"
    payment = initiate(client, headers_a, order["id"], "owner-key-001")
    assert client.get(
        f"/api/v1/payments/{payment['id']}", headers=headers_b
    ).status_code == 404
    own = client.get(f"/api/v1/payments/{payment['id']}", headers=headers_a)
    assert own.status_code == 200
    assert own.json()["order_id"] == order["id"]


def test_khata_immutable_no_write_routes(client: TestClient):
    _, headers = make_farmer("9300000009")
    fake_id = str(uuid.uuid4())
    assert client.post("/api/v1/khata/entries", json={}, headers=headers).status_code in (404, 405)
    assert client.put(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.patch(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.delete(
        f"/api/v1/khata/entries/{fake_id}", headers=headers
    ).status_code in (404, 405)
    assert client.post("/api/v1/khata/summary", json={}, headers=headers).status_code in (404, 405)
    assert client.delete("/api/v1/khata/summary", headers=headers).status_code in (404, 405)


def test_initiate_rejects_non_pending_and_short_key(client: TestClient):
    _, headers = make_farmer("9300000010")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "paid-key-0001")
    assert client.post(
        "/api/v1/payments/webhook",
        json=_signed_webhook(payment["provider_ref"], "success"),
    ).status_code == 200
    repeat = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "paid-key-0002"},
        headers=headers,
    )
    assert repeat.status_code == 422
    assert repeat.json()["error"]["code"] == "PAYMENT_ALREADY_PROCESSED"
    short = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "short"},
        headers=headers,
    )
    assert short.status_code == 422
