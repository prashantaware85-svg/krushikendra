"""Store catalogue + commerce edge-case tests (SQLite, scoped tables).

Covers: category 404, product search/filter, variant stock display,
image 404, product detail shape, inactive-product rules, address
phone/pincode 422s, cart qty 422s, checkout-without-address 422,
and order-history-on-cancel.
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
    app = FastAPI(title="Krushi Seva API (store-extra test)")
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
        seeds = ProductCategory(name="Seeds", description="Seed catalogue")
        tools = ProductCategory(name="Tools", description="Tool catalogue")
        db.add_all([seeds, tools])
        db.flush()
        cotton = Product(
            name="Cotton Seeds", description="Test product",
            category_id=seeds.id, base_price_paise=25000, is_active=True,
        )
        sprayer = Product(
            name="Hand Sprayer", description="Tool product",
            category_id=tools.id, base_price_paise=150000, is_active=True,
        )
        hidden = Product(
            name="Hidden Product", description="Inactive",
            category_id=seeds.id, base_price_paise=1000, is_active=False,
        )
        db.add_all([cotton, sprayer, hidden])
        db.flush()
        v1 = ProductVariant(
            product_id=cotton.id, name="1 kg", price_paise=25000, stock_qty=10
        )
        v2 = ProductVariant(
            product_id=cotton.id, name="5 kg", price_paise=120000, stock_qty=0
        )
        db.add_all([v1, v2])
        db.flush()
        db.add(ProductImage(product_id=cotton.id, image_path="missing.png", alt_text="Bag"))
        db.commit()
        return {
            "seeds": str(seeds.id), "tools": str(tools.id),
            "cotton": str(cotton.id), "sprayer": str(sprayer.id),
            "hidden": str(hidden.id), "v1": str(v1.id), "v2": str(v2.id),
        }


def make_address(client: TestClient, headers: dict) -> dict:
    response = client.post("/api/v1/store/addresses", json=ADDRESS, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_category_detail_404(client: TestClient):
    seed_catalog()
    _, headers = make_farmer("9200000001")
    response = client.get(f"/api/v1/store/categories/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "STORE_CATEGORY_NOT_FOUND"


def test_product_search_filter(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000002")
    response = client.get("/api/v1/store/products?search=cotton", headers=headers)
    assert response.status_code == 200, response.text
    names = [p["name"] for p in response.json()["products"]]
    assert names == ["Cotton Seeds"]
    response = client.get(
        f"/api/v1/store/products?category_id={ids['tools']}", headers=headers
    )
    assert response.status_code == 200, response.text
    assert [p["name"] for p in response.json()["products"]] == ["Hand Sprayer"]


def test_variant_stock_display(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000003")
    response = client.get(
        f"/api/v1/store/products/{ids['cotton']}/variants", headers=headers
    )
    assert response.status_code == 200, response.text
    by_name = {v["name"]: v for v in response.json()}
    assert by_name["1 kg"]["stock_qty"] == 10
    assert by_name["5 kg"]["stock_qty"] == 0  # zero stock still displayed


def test_image_serve_404(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000004")
    # Unknown image id → 404.
    response = client.get(f"/api/v1/store/images/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "STORE_IMAGE_NOT_FOUND"
    # Known row but file absent on disk → 404 as well.
    images = client.get(
        f"/api/v1/store/products/{ids['cotton']}/images", headers=headers
    ).json()
    assert len(images) == 1
    response = client.get(f"/api/v1/store/images/{images[0]['id']}", headers=headers)
    assert response.status_code == 404


def test_product_detail_includes_variants_images(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000005")
    response = client.get(f"/api/v1/store/products/{ids['cotton']}", headers=headers)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert len(detail["variants"]) == 2
    assert {v["name"] for v in detail["variants"]} == {"1 kg", "5 kg"}
    assert len(detail["images"]) == 1
    assert detail["images"][0]["alt_text"] == "Bag"


def test_inactive_product_hidden_rules(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000006")
    listed = client.get("/api/v1/store/products", headers=headers).json()["products"]
    assert "Hidden Product" not in [p["name"] for p in listed]
    for path in (
        f"/api/v1/store/products/{ids['hidden']}",
        f"/api/v1/store/products/{ids['hidden']}/variants",
        f"/api/v1/store/products/{ids['hidden']}/images",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["error"]["code"] == "STORE_PRODUCT_NOT_FOUND"


def test_address_phone_pincode_validation_422(client: TestClient):
    seed_catalog()
    _, headers = make_farmer("9200000007")
    bad_phone = dict(ADDRESS, phone="123")
    response = client.post("/api/v1/store/addresses", json=bad_phone, headers=headers)
    assert response.status_code == 422, response.text
    bad_pin = dict(ADDRESS, pincode="4220")
    response = client.post("/api/v1/store/addresses", json=bad_pin, headers=headers)
    assert response.status_code == 422, response.text
    assert client.get("/api/v1/store/addresses", headers=headers).json() == []


def test_cart_qty_validation_422(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000008")
    for qty in (0, -2):
        response = client.post(
            "/api/v1/store/cart/items",
            json={"variant_id": ids["v1"], "qty": qty},
            headers=headers,
        )
        assert response.status_code == 422, (qty, response.text)
        assert response.json()["error"]["code"] == "QTY_LIMIT"


def test_checkout_without_address_422(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000009")
    # Missing address_id field → schema 422.
    response = client.post("/api/v1/store/checkout", json={}, headers=headers)
    assert response.status_code == 422, response.text
    # Valid address but empty cart → CART_EMPTY 422.
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "CART_EMPTY"
    # Unknown address id with a filled cart → 404 (address leg).
    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    )
    response = client.post(
        "/api/v1/store/checkout",
        json={"address_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404, response.text


def test_order_history_appended_on_cancel(client: TestClient):
    ids = seed_catalog()
    _, headers = make_farmer("9200000010")
    client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": ids["v1"], "qty": 1},
        headers=headers,
    )
    address = make_address(client, headers)
    order = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    ).json()
    cancelled = client.post(
        f"/api/v1/store/orders/{order['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    with TestingSession() as db:
        history = (
            db.query(OrderStatusHistory)
            .filter(OrderStatusHistory.order_id == uuid.UUID(order["id"]))
            .all()
        )
        pairs = [(h.from_status, h.to_status) for h in history]
        assert len(pairs) == 2
        assert (None, "pending") in pairs
        assert ("pending", "cancelled") in pairs
