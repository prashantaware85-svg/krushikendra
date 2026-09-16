"""Khata ledger edge-case tests (SQLite, scoped tables).

Covers: zero summary for new farmers, entries pagination, immutability,
balance_after snapshots across a debit+payment sequence (webhook posts
always carry a valid HMAC — never unsigned), over-limit flag, farmer
isolation, and note preservation.
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

WEBHOOK_SECRET = "khata-extra-secret"


@pytest.fixture()
def webhook_secret():
    settings = get_settings()
    old = settings.payment_webhook_secret
    settings.payment_webhook_secret = WEBHOOK_SECRET
    try:
        yield WEBHOOK_SECRET
    finally:
        settings.payment_webhook_secret = old


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (khata-extra test)")
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


def signed_webhook(client: TestClient, provider_ref: str, status: str) -> dict:
    signature = hmac.new(
        WEBHOOK_SECRET.encode(), f"{provider_ref}.{status}".encode(), hashlib.sha256
    ).hexdigest()
    response = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": provider_ref, "status": status, "signature": signature},
    )
    assert response.status_code == 200, response.text
    return response.json()


def checkout_and_pay(client: TestClient, headers: dict, *, price: int = 2000) -> dict:
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
    order = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    ).json()
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": f"key-{order['id']}"},
        headers=headers,
    ).json()
    signed_webhook(client, payment["provider_ref"], "success")
    return order


def entries(client: TestClient, headers: dict, qs: str = "") -> dict:
    response = client.get(f"/api/v1/khata/entries{qs}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_zeros_for_new_farmer(client: TestClient):
    _, headers = make_farmer("9300000001")
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["total_debits_paise"] == 0
    assert summary["total_credits_paise"] == 0
    assert summary["total_payments_paise"] == 0
    assert summary["outstanding_paise"] == 0
    assert summary["over_limit"] is False
    assert entries(client, headers)["entries"] == []


def test_entries_pagination_limit_offset(client: TestClient):
    farmer_id, headers = make_farmer("9300000002")
    with TestingSession() as db:
        for i in range(5):
            khata_service.record_debit(
                db, farmer_id=farmer_id, amount_paise=100 * (i + 1), note=f"debit-{i}"
            )
    page = entries(client, headers, "?limit=2&offset=0")
    assert page["total"] == 5
    assert page["limit"] == 2 and page["offset"] == 0
    assert len(page["entries"]) == 2
    tail = entries(client, headers, "?limit=2&offset=4")
    assert len(tail["entries"]) == 1
    assert tail["offset"] == 4
    # Pages tile without overlap.
    first_ids = [e["id"] for e in page["entries"]]
    assert all(e["id"] not in first_ids for e in tail["entries"])


def test_entries_immutable(client: TestClient):
    _, headers = make_farmer("9300000003")
    assert client.post("/api/v1/khata/entries", json={}, headers=headers).status_code in (
        404, 405,
    )
    fake_id = str(uuid.uuid4())
    assert client.put(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=headers
    ).status_code in (404, 405)
    assert client.delete(
        f"/api/v1/khata/entries/{fake_id}", headers=headers
    ).status_code in (404, 405)


def test_balance_after_snapshot_debit_payment_sequence(
    client: TestClient, webhook_secret: str
):
    farmer_id, headers = make_farmer("9300000004")
    with TestingSession() as db:
        khata_service.record_debit(
            db, farmer_id=farmer_id, amount_paise=5000, note="owed"
        )
    order = checkout_and_pay(client, headers, price=2000)
    page = entries(client, headers)
    assert page["total"] == 2
    by_type = {e["entry_type"]: e for e in page["entries"]}
    assert by_type["debit"]["balance_after_paise"] == -5000
    assert by_type["debit"]["amount_paise"] == 5000
    assert by_type["payment"]["balance_after_paise"] == -3000  # -5000 + 2000
    assert by_type["payment"]["amount_paise"] == order["total_paise"]
    assert by_type["payment"]["order_id"] == order["id"]
    # Newest first: payment before debit.
    assert [e["entry_type"] for e in page["entries"]] == ["payment", "debit"]
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["outstanding_paise"] == 3000


def test_over_limit_flag_with_credit_limit(client: TestClient):
    farmer_id, headers = make_farmer("9300000005")
    with TestingSession() as db:
        khata_service.record_debit(db, farmer_id=farmer_id, amount_paise=5000)
    # Default limit is 0 → any outstanding is over limit.
    assert client.get("/api/v1/khata/summary", headers=headers).json()["over_limit"] is True
    settings = get_settings()
    old = settings.khata_credit_limit
    settings.khata_credit_limit = 10000
    try:
        assert (
            client.get("/api/v1/khata/summary", headers=headers).json()["over_limit"]
            is False
        )
    finally:
        settings.khata_credit_limit = old
    # A covering credit clears the flag even at the default limit.
    with TestingSession() as db:
        khata_service.record_credit(db, farmer_id=farmer_id, amount_paise=5000)
    summary = client.get("/api/v1/khata/summary", headers=headers).json()
    assert summary["outstanding_paise"] == 0
    assert summary["over_limit"] is False


def test_farmer_isolation(client: TestClient):
    farmer_a, headers_a = make_farmer("9300000006")
    _, headers_b = make_farmer("9300000007")
    with TestingSession() as db:
        khata_service.record_debit(
            db, farmer_id=farmer_a, amount_paise=1500, note="A owes"
        )
    assert client.get("/api/v1/khata/summary", headers=headers_a).json()[
        "outstanding_paise"
    ] == 1500
    other = client.get("/api/v1/khata/summary", headers=headers_b).json()
    assert other["outstanding_paise"] == 0
    assert other["total_debits_paise"] == 0
    assert entries(client, headers_b)["entries"] == []


def test_note_preserved(client: TestClient):
    farmer_id, headers = make_farmer("9300000008")
    with TestingSession() as db:
        khata_service.record_debit(
            db, farmer_id=farmer_id, amount_paise=750, note="fertilizer advance"
        )
    page = entries(client, headers)
    assert page["total"] == 1
    assert page["entries"][0]["note"] == "fertilizer advance"
    assert page["entries"][0]["amount_paise"] == 750


def test_khata_requires_auth(client: TestClient):
    assert client.get("/api/v1/khata/summary").status_code == 401
    assert client.get("/api/v1/khata/entries").status_code == 401
