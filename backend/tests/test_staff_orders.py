"""Step 18 staff order-view tests (SQLite, scoped tables, minimal app).

Test-only file: no app code, migrations, or existing tests touched.

Pattern (from tests/test_rbac.py): minimal FastAPI app mounting the
staff + commerce + suppliers + purchases + inventory + payments + khata
routers, per-test SQLite schema, real JWT farmers via DB rows +
``create_access_token``, staff seeded as active ``StoreStaff`` rows via
``make_staff``.

Covers: admin/manager/staff read-only store order views (list/detail/
items), staff+manager order/payment immutability, cross-store rejection,
farmer access unchanged, payments webhook HMAC + khata GET-only intact.
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
from app.models.auth import FarmerProfile, User
from app.models.commerce import (
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderCounter,
    OrderItem,
    OrderStatusHistory,
)
from app.models.inventory import DEFAULT_STORE_ID, InventoryItem, Purchase, PurchaseItem, Supplier
from app.models.khata import KhataEntry
from app.models.payments import Payment
from app.models.staff import StoreAuditLog, StoreStaff
from app.models.store import Product, ProductCategory, ProductVariant
from app.modules.commerce.router import router as commerce_router
from app.modules.inventory.router import router as inventory_router
from app.modules.khata.router import router as khata_router
from app.modules.payments.router import router as payments_router
from app.modules.purchases.router import router as purchases_router
from app.modules.staff.router import router as staff_router
from app.modules.suppliers.router import router as suppliers_router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

TABLES = [
    User.__table__,
    FarmerProfile.__table__,
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
    Supplier.__table__,
    Purchase.__table__,
    PurchaseItem.__table__,
    InventoryItem.__table__,
    StoreStaff.__table__,
    StoreAuditLog.__table__,
    Payment.__table__,
    KhataEntry.__table__,
]

from app.models.inventory import StockMovement  # noqa: E402,F401

TABLES.append(StockMovement.__table__)

ADDRESS = {
    "label": "Home",
    "line1": "123 Farm Road",
    "city": "Nashik",
    "state": "Maharashtra",
    "pincode": "422001",
    "phone": "9876543210",
}

STAFF_ORDERS = "/api/v1/store/staff/orders"
FARMER_ORDERS = "/api/v1/store/orders"

_WEBHOOK_SECRET = "test-staff-orders-webhook-secret"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (staff orders test)")
    register_exception_handlers(app)
    app.include_router(staff_router, prefix="/api/v1")
    app.include_router(commerce_router, prefix="/api/v1")
    app.include_router(suppliers_router, prefix="/api/v1")
    app.include_router(purchases_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(khata_router, prefix="/api/v1")
    return app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=TABLES)
    Base.metadata.create_all(bind=engine, tables=TABLES)
    settings = get_settings()
    old_allowlist = settings.store_staff_mobiles
    old_webhook_secret = settings.payment_webhook_secret
    settings.store_staff_mobiles = ""
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
    settings.store_staff_mobiles = old_allowlist
    settings.payment_webhook_secret = old_webhook_secret


def make_farmer(mobile: str) -> tuple[User, dict]:
    from app.modules.auth.security import create_access_token

    with TestingSession() as db:
        user = User(mobile_number=mobile, is_verified=True, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(str(user.id), get_settings())
        return user, {"Authorization": f"Bearer {token}"}


def make_staff(mobile: str, role: str = "admin") -> tuple[User, dict]:
    """DB RBAC: staff = active StoreStaff row (allowlist retired)."""
    user, headers = make_farmer(mobile)
    with TestingSession() as db:
        existing = (
            db.query(StoreStaff)
            .filter(
                StoreStaff.store_id == DEFAULT_STORE_ID,
                StoreStaff.user_id == user.id,
            )
            .one_or_none()
        )
        if existing is None:
            db.add(
                StoreStaff(
                    store_id=DEFAULT_STORE_ID,
                    user_id=user.id,
                    role=role,
                    is_active=True,
                )
            )
            db.commit()
    return user, headers


def seed_catalog() -> dict:
    with TestingSession() as db:
        category = ProductCategory(name="Seeds", description="staff-orders catalogue")
        db.add(category)
        db.flush()
        product = Product(
            name="Cotton Seeds",
            description="staff-orders product",
            category_id=category.id,
            base_price_paise=25000,
            is_active=True,
        )
        db.add(product)
        db.flush()
        v1 = ProductVariant(
            product_id=product.id, name="1 kg", price_paise=25000, stock_qty=100
        )
        db.add(v1)
        db.commit()
        return {"product": str(product.id), "v1": str(v1.id)}


def checkout(client: TestClient, headers: dict, variant_id: str, qty: int = 1) -> dict:
    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": variant_id, "qty": qty},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    address = client.post(
        "/api/v1/store/addresses", json=ADDRESS, headers=headers
    )
    assert address.status_code == 201, address.text
    response = client.post(
        "/api/v1/store/checkout",
        json={"address_id": address.json()["id"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sign(ref: str, status_value: str) -> str:
    return hmac.new(
        _WEBHOOK_SECRET.encode(), f"{ref}.{status_value}".encode(), hashlib.sha256
    ).hexdigest()


# ── 1: admin views store orders ──────────────────────────────────────
def test_staff_orders_admin_views_store_orders(client: TestClient):
    _, admin = make_staff("9300000201", "admin")
    _, farmer = make_farmer("9300000202")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    response = client.get(STAFF_ORDERS, headers=admin)
    assert response.status_code == 200, response.text
    listed = response.json()
    assert any(o["id"] == order["id"] for o in listed)


# ── 2: manager views store orders ────────────────────────────────────
def test_staff_orders_manager_views_store_orders(client: TestClient):
    _, manager = make_staff("9300000203", "store_manager")
    _, farmer = make_farmer("9300000204")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    response = client.get(STAFF_ORDERS, headers=manager)
    assert response.status_code == 200, response.text
    assert any(o["id"] == order["id"] for o in response.json())


# ── 3: staff views list + detail + items ─────────────────────────────
def test_staff_orders_staff_views_detail_and_items(client: TestClient):
    _, staff = make_staff("9300000205", "store_staff")
    _, farmer = make_farmer("9300000206")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    listed = client.get(STAFF_ORDERS, headers=staff)
    assert listed.status_code == 200, listed.text
    assert any(o["id"] == order["id"] for o in listed.json())
    detail = client.get(f"{STAFF_ORDERS}/{order['id']}", headers=staff)
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == order["id"]
    items = client.get(f"{STAFF_ORDERS}/{order['id']}/items", headers=staff)
    assert items.status_code == 200, items.text
    assert len(items.json()) >= 1


# ── 4: staff cannot modify order ─────────────────────────────────────
def test_staff_orders_staff_cannot_modify_order(client: TestClient):
    _, staff = make_staff("9300000207", "store_staff")
    _, farmer = make_farmer("9300000208")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    # Staff is not the order owner: farmer-scoped cancel surfaces as 404.
    response = client.post(
        f"{FARMER_ORDERS}/{order['id']}/cancel", headers=staff
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
    # No PUT/DELETE verbs exist on the read-only staff order paths.
    response = client.put(f"{STAFF_ORDERS}/{order['id']}", json={}, headers=staff)
    assert response.status_code in (404, 405), response.text
    response = client.delete(f"{STAFF_ORDERS}/{order['id']}", headers=staff)
    assert response.status_code in (404, 405), response.text


# ── 5: staff cannot modify payment ───────────────────────────────────
def test_staff_orders_staff_cannot_modify_payment(client: TestClient):
    _, staff = make_staff("9300000209", "store_staff")
    _, farmer = make_farmer("9300000210")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    # No staff-scoped payment write paths exist.
    response = client.post("/api/v1/store/staff/payments", json={}, headers=staff)
    assert response.status_code in (404, 405), response.text
    response = client.patch("/api/v1/store/staff/payments", json={}, headers=staff)
    assert response.status_code in (404, 405), response.text
    # Staff cannot initiate payment for another farmer's order.
    response = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "staff-pay-0001"},
        headers=staff,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


# ── 6: manager cannot modify payment ─────────────────────────────────
def test_staff_orders_manager_cannot_modify_payment(client: TestClient):
    _, manager = make_staff("9300000211", "store_manager")
    _, farmer = make_farmer("9300000212")
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    response = client.post("/api/v1/store/staff/payments", json={}, headers=manager)
    assert response.status_code in (404, 405), response.text
    response = client.patch("/api/v1/store/staff/payments", json={}, headers=manager)
    assert response.status_code in (404, 405), response.text
    response = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "mgr-pay-0001"},
        headers=manager,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


# ── 7: cross-store staff gets nothing ────────────────────────────────
def test_staff_orders_cross_store_no_access(client: TestClient):
    _, farmer = make_farmer("9300000213")
    outsider, outsider_headers = make_farmer("9300000214")
    other_store = uuid.uuid4()
    with TestingSession() as db:
        db.add(
            StoreStaff(
                store_id=other_store,
                user_id=outsider.id,
                role="store_staff",
                is_active=True,
            )
        )
        db.commit()
    ids = seed_catalog()
    order = checkout(client, farmer, ids["v1"], qty=1)
    # Other-store row grants nothing on this store: 403 at the gate
    # (404 if scope-checked first); either way no order data leaks.
    response = client.get(STAFF_ORDERS, headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    assert order["id"] not in response.text
    response = client.get(f"{STAFF_ORDERS}/{order['id']}", headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    assert order["id"] not in response.text


# ── 8: farmer access unchanged ───────────────────────────────────────
def test_staff_orders_farmer_access_unchanged(client: TestClient):
    _, farmer_a = make_farmer("9300000215")
    _, farmer_b = make_farmer("9300000216")
    ids = seed_catalog()
    order = checkout(client, farmer_a, ids["v1"], qty=1)
    listed = client.get(FARMER_ORDERS, headers=farmer_a).json()
    assert any(o["id"] == order["id"] for o in listed)
    response = client.get(f"{FARMER_ORDERS}/{order['id']}", headers=farmer_b)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
    listed_b = client.get(FARMER_ORDERS, headers=farmer_b).json()
    assert all(o["id"] != order["id"] for o in listed_b)
    assert client.get(FARMER_ORDERS).status_code == 401


# ── 9: payments webhook intact ───────────────────────────────────────
def test_staff_orders_payments_webhook_intact(client: TestClient):
    get_settings().payment_webhook_secret = _WEBHOOK_SECRET
    ids = seed_catalog()
    _, farmer = make_farmer("9300000217")
    order = checkout(client, farmer, ids["v1"], qty=1)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "staff-orders-key-01"},
        headers=farmer,
    )
    assert payment.status_code == 201, payment.text
    ref = payment.json()["provider_ref"]
    unsigned = client.post(
        "/api/v1/payments/webhook",
        json={"provider_ref": ref, "status": "success"},
    )
    assert unsigned.status_code == 401, unsigned.text
    signed = client.post(
        "/api/v1/payments/webhook",
        json={
            "provider_ref": ref,
            "status": "success",
            "signature": _sign(ref, "success"),
        },
    )
    assert signed.status_code == 200, signed.text


# ── 10: khata GET-only + farmer-scoped ───────────────────────────────
def test_staff_orders_khata_get_only_intact(client: TestClient):
    get_settings().payment_webhook_secret = _WEBHOOK_SECRET
    ids = seed_catalog()
    _, farmer_a = make_farmer("9300000218")
    _, farmer_b = make_farmer("9300000219")
    fake_id = str(uuid.uuid4())
    assert client.post("/api/v1/khata/entries", json={}, headers=farmer_a).status_code in (404, 405)
    assert client.put(f"/api/v1/khata/entries/{fake_id}", json={}, headers=farmer_a).status_code in (404, 405)
    assert client.delete(f"/api/v1/khata/entries/{fake_id}", headers=farmer_a).status_code in (404, 405)
    order = checkout(client, farmer_a, ids["v1"], qty=1)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "staff-orders-khata-01"},
        headers=farmer_a,
    ).json()
    assert client.post(
        "/api/v1/payments/webhook",
        json={
            "provider_ref": payment["provider_ref"],
            "status": "success",
            "signature": _sign(payment["provider_ref"], "success"),
        },
    ).status_code == 200
    entries_a = client.get("/api/v1/khata/entries", headers=farmer_a).json()["entries"]
    entries_b = client.get("/api/v1/khata/entries", headers=farmer_b).json()["entries"]
    assert len(entries_a) == 1
    assert entries_b == []
