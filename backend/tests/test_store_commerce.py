"""Store catalogue + cart/orders tests (SQLite, scoped tables, minimal app).

Follows the auth-foundation pattern: a minimal FastAPI app mounting ONLY the
store + commerce routers, so sibling domains under parallel rebuild cannot
break this suite.
"""

from __future__ import annotations

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
from app.models.store import Product, ProductCategory, ProductImage, ProductVariant
from app.modules.commerce import service as commerce_service
from app.modules.commerce.router import router as commerce_router
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
    ProductImage.__table__,
    Cart.__table__,
    CartItem.__table__,
    DeliveryAddress.__table__,
    Order.__table__,
    OrderItem.__table__,
    OrderStatusHistory.__table__,
    OrderCounter.__table__,
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
    app = FastAPI(title="Krushi Seva API (store/commerce test)")
    register_exception_handlers(app)
    app.include_router(store_router, prefix="/api/v1")
    app.include_router(commerce_router, prefix="/api/v1")
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


def make_farmer(mobile: str) -> tuple[User, dict]:
    from app.modules.auth.security import create_access_token

    with TestingSession() as db:
        user = User(mobile_number=mobile, is_verified=True, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(str(user.id), get_settings())
        return user, {"Authorization": f"Bearer {token}"}


def seed_catalog() -> dict:
    with TestingSession() as db:
        category = ProductCategory(name="Seeds", description="Test catalogue")
        db.add(category)
        db.flush()
        active = Product(
            name="Cotton Seeds",
            description="Test product",
            category_id=category.id,
            base_price_paise=25000,
            is_active=True,
        )
        hidden = Product(
            name="Hidden Product",
            description="Inactive",
            category_id=category.id,
            base_price_paise=1000,
            is_active=False,
        )
        db.add_all([active, hidden])
        db.flush()
        v1 = ProductVariant(
            product_id=active.id, name="1 kg", price_paise=25000, stock_qty=10
        )
        v_null = ProductVariant(
            product_id=active.id, name="Bulk", price_paise=None, stock_qty=5
        )
        v_low = ProductVariant(
            product_id=active.id, name="500 g", price_paise=10000, stock_qty=1
        )
        db.add_all([v1, v_null, v_low])
        db.flush()
        db.add(
            ProductImage(
                product_id=active.id, image_path="missing.png", alt_text="Test"
            )
        )
        db.commit()
        return {
            "product": str(active.id),
            "hidden": str(hidden.id),
            "v1": str(v1.id),
            "v_null": str(v_null.id),
            "v_low": str(v_low.id),
        }


def make_address(client: TestClient, headers: dict) -> dict:
    response = client.post("/api/v1/store/addresses", json=ADDRESS, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ── Catalogue ─────────────────────────────────────────────────────────
def test_catalogue_read_and_auth(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9000000001")

    response = client.get("/api/v1/store/products", headers=headers)
    assert response.status_code == 200, response.text
    names = [p["name"] for p in response.json()["products"]]
    assert "Cotton Seeds" in names
    assert "Hidden Product" not in names  # inactive never listed

    response = client.get(f"/api/v1/store/products/{ids['product']}", headers=headers)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert len(detail["variants"]) == 3
    assert detail["images"] and detail["images"][0]["alt_text"] == "Test"

    response = client.get(f"/api/v1/store/products/{ids['hidden']}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STORE_PRODUCT_NOT_FOUND"

    response = client.get("/api/v1/store/products")  # no token
    assert response.status_code == 401

    response = client.get("/api/v1/store/categories", headers=headers)
    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Seeds"]


# ── Cart validation ───────────────────────────────────────────────────
def test_cart_validate_totals_and_null_price(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9000000002")

    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 2},
        headers=headers,
    )
    assert response.status_code == 201, response.text

    response = client.post("/api/v1/store/cart/validate", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"valid": True, "issues": [], "subtotal_paise": 50000}

    # NULL price → unorderable, reported (never silently dropped).
    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v_null"], "qty": 1},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = client.post("/api/v1/store/cart/validate", headers=headers).json()
    assert body["valid"] is False
    assert [i["code"] for i in body["issues"]] == ["PRICE_ON_REQUEST"]
    assert body["subtotal_paise"] == 50000  # only orderable lines counted

    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CART_INVALID"


def test_stock_and_qty_rules(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9000000003")

    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v_low"], "qty": 2},
        headers=headers,
    )
    body = client.post("/api/v1/store/cart/validate", headers=headers).json()
    assert [i["code"] for i in body["issues"]] == ["INSUFFICIENT_STOCK"]

    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 101},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QTY_LIMIT"

    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": str(uuid.uuid4()), "qty": 1},
        headers=headers,
    )
    assert response.status_code == 404


# ── Checkout ──────────────────────────────────────────────────────────
def test_checkout_transaction_success(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9000000004")

    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 2},
        headers=headers,
    )
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["subtotal_paise"] == 50000
    assert order["total_paise"] == 50000  # delivery 0 in dev config
    assert order["status"] == "pending"
    assert order["payment_status"] == "pending"  # NO payments inside commerce
    assert order["payment_ref"] is None
    assert order["order_number"] == "KS-000001"
    assert order["items"][0]["unit_price_paise"] == 25000
    assert order["items"][0]["line_total_paise"] == 50000

    # Cart cleared, history recorded.
    cart = client.get("/api/v1/store/cart", headers=headers).json()
    assert cart["items"] == [] and cart["subtotal_paise"] == 0
    with TestingSession() as db:
        history = (
            db.query(OrderStatusHistory)
            .filter(OrderStatusHistory.order_id == uuid.UUID(order["id"]))
            .all()
        )
        assert [(h.from_status, h.to_status) for h in history] == [(None, "pending")]


def test_checkout_ignores_tampered_totals(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9000000005")

    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    )
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout",
        json={
            "address_id": address["id"],
            "total_paise": 1,
            "payment_status": "paid",
            "payment_ref": "fake",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["total_paise"] == 25000  # server math wins
    assert order["payment_status"] == "pending"
    assert order["payment_ref"] is None


# ── Cancel rules ──────────────────────────────────────────────────────
def test_cancel_rules(client: TestClient):
    ids = seed_catalog()
    user, headers = make_farmer("9000000006")

    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    )
    address = make_address(client, headers)
    order = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    ).json()

    response = client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    response = client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ORDER_CANCEL_INVALID"

    # Shipped orders cannot be cancelled (admin transition, service-level).
    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    )
    order2 = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    ).json()
    with TestingSession() as db:
        orm_order = db.get(Order, uuid.UUID(order2["id"]))
        assert orm_order is not None and orm_order.farmer_user_id == user.id
        commerce_service.transition_order(db, orm_order, "confirmed")
        commerce_service.transition_order(db, orm_order, "shipped")
    response = client.post(
        f"/api/v1/store/orders/{order2['id']}/cancel", headers=headers
    )
    assert response.status_code == 422


# ── Isolation + addresses ─────────────────────────────────────────────
def test_cross_farmer_isolation(client: TestClient):
    ids = seed_catalog()
    _, headers_a = make_farmer("9000000007")
    _, headers_b = make_farmer("9000000008")

    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers_a,
    )
    address = make_address(client, headers_a)
    order = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers_a
    ).json()

    assert client.get(f"/api/v1/store/orders/{order['id']}", headers=headers_b).status_code == 404
    cart_b = client.get("/api/v1/store/cart", headers=headers_b).json()
    assert cart_b["items"] == []  # separate cart
    assert client.get("/api/v1/store/addresses", headers=headers_b).json() == []


def test_address_default_handoff(client: TestClient):
    seed_catalog()
    _, headers = make_farmer("9000000009")

    first = make_address(client, headers)
    assert first["is_default"] is True
    second_payload = dict(ADDRESS, label="Farm", phone="9123456789")
    second = client.post(
        "/api/v1/store/addresses", json=second_payload, headers=headers
    ).json()
    assert second["is_default"] is False

    promoted = client.post(
        f"/api/v1/store/addresses/{second['id']}/default", headers=headers
    ).json()
    assert promoted["is_default"] is True

    response = client.delete(
        f"/api/v1/store/addresses/{second['id']}", headers=headers
    )
    assert response.status_code == 204
    remaining = client.get("/api/v1/store/addresses", headers=headers).json()
    assert len(remaining) == 1 and remaining[0]["is_default"] is True
