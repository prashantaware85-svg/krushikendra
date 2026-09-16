"""Commerce security tests: isolation, server-side totals, stock, rules (SQLite).

Follows tests/test_store_commerce.py exactly: a minimal FastAPI app mounting
ONLY the store + commerce routers, scoped TABLES, farmers minted via real
DB rows + ``create_access_token``.
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
from app.models.store import Product, ProductCategory, ProductVariant
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
    app = FastAPI(title="Krushi Seva API (commerce security test)")
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


def seed_catalog(stock_v1: int = 10) -> dict:
    with TestingSession() as db:
        category = ProductCategory(name=f"Seeds-{uuid.uuid4().hex[:6]}")
        db.add(category)
        db.flush()
        active = Product(
            name=f"Cotton-{uuid.uuid4().hex[:6]}",
            category_id=category.id,
            base_price_paise=25000,
            is_active=True,
        )
        db.add(active)
        db.flush()
        v1 = ProductVariant(
            product_id=active.id, name="1 kg", price_paise=25000, stock_qty=stock_v1
        )
        v_null = ProductVariant(
            product_id=active.id, name="Bulk", price_paise=None, stock_qty=5
        )
        db.add_all([v1, v_null])
        db.commit()
        return {"product": str(active.id), "v1": str(v1.id), "v_null": str(v_null.id)}


def make_address(client: TestClient, headers: dict) -> dict:
    response = client.post("/api/v1/store/addresses", json=ADDRESS, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def checkout(client: TestClient, headers: dict, variant_id: str, qty: int = 1) -> dict:
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": variant_id, "qty": qty},
        headers=headers,
    ).status_code == 201
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_farmer_cart_isolation_and_item_404(client: TestClient):
    ids = seed_catalog()
    _, headers_a = make_farmer("9200000001")
    _, headers_b = make_farmer("9200000002")
    added = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 2},
        headers=headers_a,
    )
    assert added.status_code == 201, added.text
    item_id = added.json()["item_id"]
    cart_b = client.get("/api/v1/store/cart", headers=headers_b).json()
    assert cart_b["items"] == [] and cart_b["subtotal_paise"] == 0
    assert client.put(
        f"/api/v1/store/cart/items/{item_id}", json={"qty": 1}, headers=headers_b
    ).status_code == 404
    assert client.delete(
        f"/api/v1/store/cart/items/{item_id}", headers=headers_b
    ).status_code == 404
    # Owner cart untouched by the stranger's attempts.
    assert client.get("/api/v1/store/cart", headers=headers_a).json()["subtotal_paise"] == 50000


def test_checkout_null_price_cart_422(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000003")
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v_null"], "qty": 1},
        headers=headers,
    ).status_code == 201
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CART_INVALID"


def test_checkout_ignores_tampered_totals_and_status(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000004")
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 2},
        headers=headers,
    ).status_code == 201
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout",
        json={"address_id": address["id"], "total_paise": 1,
              "payment_status": "paid", "payment_ref": "fake"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["total_paise"] == 50000  # server math wins
    assert order["payment_status"] == "pending"
    assert order["payment_ref"] is None


def test_checkout_uses_live_variant_price(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000005")
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    ).status_code == 201
    with TestingSession() as db:
        variant = db.get(ProductVariant, uuid.UUID(ids["v1"]))
        assert variant is not None
        variant.price_paise = 30000
        db.commit()
    address = make_address(client, headers)
    order = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    ).json()
    assert order["subtotal_paise"] == 30000
    assert order["total_paise"] == 30000


def test_zero_stock_blocks_checkout(client: TestClient):
    ids = seed_catalog(stock_v1=0)
    _, headers = make_farmer("9200000006")
    assert client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    ).status_code == 201
    body = client.post("/api/v1/store/cart/validate", headers=headers).json()
    assert body["valid"] is False
    assert [i["code"] for i in body["issues"]] == ["INSUFFICIENT_STOCK"]
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CART_INVALID"


def test_address_cross_farmer_404(client: TestClient):
    ids = seed_catalog()
    _, headers_a = make_farmer("9200000007")
    _, headers_b = make_farmer("9200000008")
    address = make_address(client, headers_a)
    assert client.put(
        f"/api/v1/store/addresses/{address['id']}", json={"city": "Pune"}, headers=headers_b
    ).status_code == 404
    assert client.post(
        f"/api/v1/store/addresses/{address['id']}/default", headers=headers_b
    ).status_code == 404
    assert client.delete(
        f"/api/v1/store/addresses/{address['id']}", headers=headers_b
    ).status_code == 404
    # Owner address untouched.
    assert client.get("/api/v1/store/addresses", headers=headers_a).json()[0]["city"] == "Nashik"


def test_address_validation_and_default_stability(client: TestClient):
    seed_catalog()
    _, headers = make_farmer("9200000009")
    bad_phone = dict(ADDRESS, phone="123")
    assert client.post(
        "/api/v1/store/addresses", json=bad_phone, headers=headers
    ).status_code == 422
    bad_pin = dict(ADDRESS, pincode="42")
    assert client.post(
        "/api/v1/store/addresses", json=bad_pin, headers=headers
    ).status_code == 422
    first = make_address(client, headers)
    second = client.post(
        "/api/v1/store/addresses", json=dict(ADDRESS, label="Farm"), headers=headers
    ).json()
    assert first["is_default"] is True and second["is_default"] is False
    # Deleting the non-default keeps the default stable.
    assert client.delete(
        f"/api/v1/store/addresses/{second['id']}", headers=headers
    ).status_code == 204
    remaining = client.get("/api/v1/store/addresses", headers=headers).json()
    assert len(remaining) == 1 and remaining[0]["is_default"] is True


def test_order_cancel_state_rules_and_stranger_404(client: TestClient):
    ids = seed_catalog()
    _, headers_a = make_farmer("9200000011")
    _, headers_b = make_farmer("9200000012")
    order = checkout(client, headers_a, ids["v1"])
    assert client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers_b
    ).status_code == 404
    cancelled = client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers_a
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    again = client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers_a
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "ORDER_CANCEL_INVALID"


def test_second_farmer_cannot_read_order_or_items(client: TestClient):
    ids = seed_catalog()
    _, headers_a = make_farmer("9200000013")
    _, headers_b = make_farmer("9200000014")
    order = checkout(client, headers_a, ids["v1"])
    assert client.get(
        f"/api/v1/store/orders/{order['id']}", headers=headers_b
    ).status_code == 404
    assert client.get(
        f"/api/v1/store/orders/{order['id']}/items", headers=headers_b
    ).status_code == 404
    assert all(
        o["id"] != order["id"]
        for o in client.get("/api/v1/store/orders", headers=headers_b).json()
    )
    own = client.get(f"/api/v1/store/orders/{order['id']}", headers=headers_a)
    assert own.status_code == 200
    assert own.json()["items"] and own.json()["items"][0]["qty"] == 1


def test_commerce_requires_auth(client: TestClient):
    assert client.get("/api/v1/store/cart").status_code == 401
    assert client.post(
        "/api/v1/store/cart/items", json={"variant_id": str(uuid.uuid4()), "qty": 1}
    ).status_code == 401
    assert client.post("/api/v1/store/cart/validate").status_code == 401
    assert client.get("/api/v1/store/orders").status_code == 401
    assert client.get("/api/v1/store/addresses").status_code == 401
    assert client.post(
        "/api/v1/store/checkout", json={"address_id": str(uuid.uuid4())}
    ).status_code == 401
