"""Webhook signing tests: fail-closed HMAC verification (SQLite, minimal app).

Follows tests/test_payments_security.py exactly: minimal FastAPI app mounting
ONLY store + commerce + payments + khata routers, scoped TABLES, farmers
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

SECRET = "signing-test-secret"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (webhook signing test)")
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


def _sig(ref: str, status_value: str, secret: str = SECRET) -> str:
    return hmac.new(
        secret.encode(), f"{ref}.{status_value}".encode(), hashlib.sha256
    ).hexdigest()


def test_production_missing_secret_rejected(client: TestClient, monkeypatch):
    _, headers = make_farmer("9400000001")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "prod-missing-01")
    ref = payment["provider_ref"]
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", "")
    monkeypatch.setattr(
        get_settings(), "payment_allow_unsigned_mock_webhook", False
    )
    response = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": ref, "status": "success"},
    )
    assert response.status_code in (401, 503), response.text
    assert response.json()["error"]["code"] == "PAYMENT_WEBHOOK_NOT_CONFIGURED"
    assert "" == get_settings().payment_webhook_secret or SECRET not in response.text


def test_dev_missing_secret_rejected_fail_closed(client: TestClient, monkeypatch):
    _, headers = make_farmer("9400000002")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "dev-missing-01")
    monkeypatch.setattr(get_settings(), "environment", "development")
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", "")
    monkeypatch.setattr(
        get_settings(), "payment_allow_unsigned_mock_webhook", False
    )
    response = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": payment["provider_ref"], "status": "success"},
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "PAYMENT_SIGNATURE_MISSING"


def test_unsigned_with_secret_rejected(client: TestClient, monkeypatch):
    _, headers = make_farmer("9400000003")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "unsigned-01")
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", SECRET)
    response = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": payment["provider_ref"], "status": "success"},
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "PAYMENT_SIGNATURE_MISSING"


def test_invalid_signature_rejected(client: TestClient, monkeypatch):
    _, headers = make_farmer("9400000004")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "invalid-01")
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", SECRET)
    response = client.post(
        "/api/v1/payments/webhook",
        json={
            "provider_ref": payment["provider_ref"],
            "status": "success",
            "signature": "wrong",
        },
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "PAYMENT_SIGNATURE_INVALID"
    assert SECRET not in response.text


def test_valid_signature_paid_and_idempotent(client: TestClient, monkeypatch):
    _, headers = make_farmer("9400000005")
    order = checkout_order(client, headers)
    payment = initiate(client, headers, order["id"], "valid-01")
    ref = payment["provider_ref"]
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", SECRET)

    good = _sig(ref, "success")
    first = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": ref, "status": "success", "signature": good},
    )
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    assert first.json()["khata_entry_id"] is not None
    assert SECRET not in first.text

    fetched = client.get(f"/api/v1/store/orders/{order['id']}", headers=headers).json()
    assert fetched["payment_status"] == "paid"

    entries = client.get("/api/v1/khata/entries", headers=headers).json()["entries"]
    assert len(entries) == 1
    assert entries[0]["amount_paise"] == order["total_paise"]

    second = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": ref, "status": "success", "signature": good},
    )
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    entries = client.get("/api/v1/khata/entries", headers=headers).json()["entries"]
    assert len(entries) == 1
    assert SECRET not in second.text
