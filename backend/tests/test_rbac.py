"""Step 17 RBAC security tests (SQLite, scoped tables, minimal app).

Test-only file: no app code, migrations, or existing tests touched.

Pattern (from tests/test_inventory.py): minimal FastAPI app mounting the
staff + commerce + suppliers + purchases + inventory + payments + khata
routers, per-test SQLite schema, real JWT farmers via DB rows +
``create_access_token``, staff seeded as active ``StoreStaff`` rows via
``make_staff`` (DB RBAC; the ``store_staff_mobiles`` allowlist is retired).

Covers: staff management gates (admin-only create/role change/
activate/deactivate/delete), last-admin guard (422 LAST_ADMIN_REQUIRED),
inactive + cross-store rejection, reorder-level (manager+), purchase
cancel (manager+) vs receive (any staff), received-purchase immutability,
adjust/supplier auth matrices, order isolation, payments webhook HMAC
intactness, khata GET-only + farmer scoping, allowlist dead, audit log.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from decimal import Decimal

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
    # StockMovement table is registered via the inventory model module.
    StoreStaff.__table__,
    StoreAuditLog.__table__,
    Payment.__table__,
    KhataEntry.__table__,
]

# StockMovement is imported for side-effect table registration only.
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

STAFF = "/api/v1/store/staff"
INV = "/api/v1/store/inventory"
SUP = "/api/v1/store/suppliers"
PUR = "/api/v1/store/purchases"

_WEBHOOK_SECRET = "test-rbac-webhook-secret"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (rbac test)")
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
    """Step 17 DB RBAC: staff = active StoreStaff row (allowlist retired)."""
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


def staff_row_id(user: User) -> str:
    with TestingSession() as db:
        row = (
            db.query(StoreStaff)
            .filter(
                StoreStaff.store_id == DEFAULT_STORE_ID,
                StoreStaff.user_id == user.id,
            )
            .one()
        )
        return str(row.id)


def audit_rows(action: str) -> list:
    with TestingSession() as db:
        return (
            db.query(StoreAuditLog)
            .filter(StoreAuditLog.action == action)
            .order_by(StoreAuditLog.created_at.asc())
            .all()
        )


def seed_catalog() -> dict:
    with TestingSession() as db:
        category = ProductCategory(name="Seeds", description="RBAC catalogue")
        db.add(category)
        db.flush()
        product = Product(
            name="Cotton Seeds",
            description="RBAC product",
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


def stock_of(variant_id: str) -> Decimal | None:
    with TestingSession() as db:
        row = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.store_id == DEFAULT_STORE_ID,
                InventoryItem.variant_id == uuid.UUID(variant_id),
            )
            .one_or_none()
        )
        return None if row is None else row.qty_on_hand


def _sign(ref: str, status_value: str) -> str:
    return hmac.new(
        _WEBHOOK_SECRET.encode(), f"{ref}.{status_value}".encode(), hashlib.sha256
    ).hexdigest()


# ── 1–6: staff management gates ──────────────────────────────────────
def test_rbac_admin_creates_staff(client: TestClient):
    _, admin = make_staff("9200000101", "admin")
    target, _ = make_farmer("9200000102")
    response = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "store_staff"
    assert body["is_active"] is True
    assert body["user_id"] == str(target.id)


def test_rbac_manager_cannot_create_staff(client: TestClient):
    _, manager = make_staff("9200000103", "store_manager")
    target, _ = make_farmer("9200000104")
    response = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=manager,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_ADMIN_REQUIRED"


def test_rbac_staff_cannot_create_staff(client: TestClient):
    _, staff = make_staff("9200000105", "store_staff")
    target, _ = make_farmer("9200000106")
    response = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=staff,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_ADMIN_REQUIRED"


def test_rbac_admin_changes_role(client: TestClient):
    _, admin = make_staff("9200000107", "admin")
    target, _ = make_farmer("9200000108")
    created = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    response = client.put(
        f"{STAFF}/{created.json()['id']}",
        json={"role": "store_manager"},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "store_manager"


def test_rbac_manager_cannot_promote_to_admin(client: TestClient):
    admin_user, admin = make_staff("9200000109", "admin")
    _, manager = make_staff("9200000110", "store_manager")
    target, _ = make_farmer("9200000111")
    created = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    # Manager promoting anyone (even to admin) must fail at the admin gate.
    response = client.put(
        f"{STAFF}/{created.json()['id']}",
        json={"role": "admin"},
        headers=manager,
    )
    assert response.status_code == 403, response.text
    # Manager cannot touch the admin's own row either.
    response = client.put(
        f"{STAFF}/{staff_row_id(admin_user)}",
        json={"role": "store_manager"},
        headers=manager,
    )
    assert response.status_code == 403, response.text


def test_rbac_staff_cannot_change_own_role(client: TestClient):
    staff_user, staff = make_staff("9200000112", "store_staff")
    _, admin = make_staff("9200000113", "admin")
    # Admin-seeded row id for the staff user; staff self-promote attempt fails.
    created = client.post(
        STAFF,
        json={"mobile_number": staff_user.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    if created.status_code == 201:
        target_id = created.json()["id"]
    else:
        target_id = staff_row_id(staff_user)
    response = client.put(
        f"{STAFF}/{target_id}", json={"role": "store_manager"}, headers=staff
    )
    assert response.status_code == 403, response.text


# ── 7–8: inactive + cross-store ──────────────────────────────────────
def test_rbac_inactive_staff_rejected(client: TestClient):
    _, admin = make_staff("9200000114", "admin")
    target, target_headers = make_farmer("9200000115")
    created = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    # Admin deactivates; the staff token must now fail closed on staff APIs.
    deactivated = client.post(
        f"{STAFF}/{created.json()['id']}/deactivate", headers=admin
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    response = client.get(STAFF, headers=target_headers)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_INACTIVE"
    ids = seed_catalog()
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 5},
        headers=target_headers,
    )
    assert response.status_code == 403, response.text


def test_rbac_cross_store_rejected(client: TestClient):
    _, admin = make_staff("9200000116", "admin")
    outsider, outsider_headers = make_farmer("9200000117")
    other_store = uuid.uuid4()
    with TestingSession() as db:
        db.add(
            StoreStaff(
                store_id=other_store,
                user_id=outsider.id,
                role="admin",
                is_active=True,
            )
        )
        db.commit()
    # Other-store admin row grants nothing on this store's staff APIs.
    response = client.get(STAFF, headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    if response.status_code == 403:
        assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"
    # ... nor on operational staff endpoints; never leaks the store's data.
    created = client.post(
        SUP, json={"name": "Home Supplier"}, headers=admin
    )
    assert created.status_code == 201, created.text
    response = client.get(SUP, headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    response = client.get(f"{SUP}/{created.json()['id']}", headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    if response.status_code == 403:
        assert "Home Supplier" not in response.text


# ── 9–11: last-admin guard + deactivate/reactivate ───────────────────
def test_rbac_last_admin_guard(client: TestClient):
    admin_user, admin = make_staff("9200000118", "admin")
    admin_id = staff_row_id(admin_user)
    response = client.put(
        f"{STAFF}/{admin_id}", json={"role": "store_staff"}, headers=admin
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"
    response = client.post(f"{STAFF}/{admin_id}/deactivate", headers=admin)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"
    response = client.delete(f"{STAFF}/{admin_id}", headers=admin)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"
    # Guard refused everything: the admin row is untouched.
    assert client.get(f"{STAFF}/{admin_id}", headers=admin).json()["is_active"] is True


def test_rbac_admin_deactivates_staff(client: TestClient):
    _, admin = make_staff("9200000119", "admin")
    target, _ = make_farmer("9200000120")
    created = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    response = client.post(
        f"{STAFF}/{created.json()['id']}/deactivate", headers=admin
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False


def test_rbac_admin_reactivates_staff(client: TestClient):
    _, admin = make_staff("9200000121", "admin")
    _, staff_headers = make_farmer("9200000122")
    target_user = None
    with TestingSession() as db:
        target_user = db.query(User).filter(
            User.mobile_number == "9200000122"
        ).one()
    created = client.post(
        STAFF,
        json={"mobile_number": "9200000122", "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    assert client.post(
        f"{STAFF}/{created.json()['id']}/deactivate", headers=admin
    ).status_code == 200
    response = client.post(
        f"{STAFF}/{created.json()['id']}/activate", headers=admin
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True
    # Reactivated staff can work again.
    ids = seed_catalog()
    assert target_user is not None
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 3},
        headers=staff_headers,
    )
    assert response.status_code == 200, response.text


# ── 12–13: reorder-level ─────────────────────────────────────────────
def test_rbac_manager_sets_reorder_level(client: TestClient):
    _, manager = make_staff("9200000123", "store_manager")
    ids = seed_catalog()
    assert client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 20},
        headers=manager,
    ).status_code == 200
    response = client.put(
        f"{INV}/{ids['v1']}/reorder-level",
        json={"reorder_level": 10},
        headers=manager,
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["reorder_level"])) == Decimal("10")


def test_rbac_staff_reorder_level_forbidden(client: TestClient):
    _, staff = make_staff("9200000124", "store_staff")
    ids = seed_catalog()
    assert client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 20},
        headers=staff,
    ).status_code == 200
    response = client.put(
        f"{INV}/{ids['v1']}/reorder-level",
        json={"reorder_level": 10},
        headers=staff,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_MANAGER_REQUIRED"


# ── 14–17: purchases ─────────────────────────────────────────────────
def test_rbac_manager_cancels_purchase(client: TestClient):
    _, manager = make_staff("9200000125", "store_manager")
    purchase = client.post(PUR, json={}, headers=manager).json()
    response = client.post(f"{PUR}/{purchase['id']}/cancel", headers=manager)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"


def test_rbac_staff_cancel_forbidden(client: TestClient):
    _, staff = make_staff("9200000126", "store_staff")
    purchase = client.post(PUR, json={}, headers=staff).json()
    response = client.post(f"{PUR}/{purchase['id']}/cancel", headers=staff)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_MANAGER_REQUIRED"
    assert client.get(f"{PUR}/{purchase['id']}", headers=staff).json()["status"] == "draft"


def test_rbac_staff_receives_purchase(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9200000127", "store_staff")
    purchase = client.post(PUR, json={}, headers=staff).json()
    assert client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 5, "unit_cost_paise": 1000},
        headers=staff,
    ).status_code == 201
    response = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "received"
    assert stock_of(ids["v1"]) == Decimal("5")


def test_rbac_received_purchase_immutable(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9200000128", "store_staff")
    purchase = client.post(PUR, json={}, headers=staff).json()
    assert client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 2, "unit_cost_paise": 1000},
        headers=staff,
    ).status_code == 201
    assert client.post(f"{PUR}/{purchase['id']}/receive", headers=staff).status_code == 200
    response = client.put(
        f"{PUR}/{purchase['id']}", json={"discount_paise": 5}, headers=staff
    )
    assert response.status_code == 422, response.text
    response = client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 1, "unit_cost_paise": 1000},
        headers=staff,
    )
    assert response.status_code == 422, response.text


# ── 18–19: adjust + supplier matrices ────────────────────────────────
def test_rbac_adjust_auth_matrix(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9200000129", "store_staff")
    _, farmer = make_farmer("9200000130")
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 4},
        headers=staff,
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 4},
        headers=farmer,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 4},
    )
    assert response.status_code == 401, response.text


def test_rbac_supplier_matrix(client: TestClient):
    _, staff = make_staff("9200000131", "store_staff")
    _, farmer = make_farmer("9200000132")
    response = client.post(SUP, json={"name": "Agro Traders"}, headers=staff)
    assert response.status_code == 201, response.text
    supplier_id = response.json()["id"]
    response = client.post(SUP, json={"name": "Nope"}, headers=farmer)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"
    # No hard-delete route exists: DELETE is 404/405 either way.
    response = client.delete(f"{SUP}/{supplier_id}", headers=staff)
    assert response.status_code in (404, 405), response.text


# ── 20: order isolation ──────────────────────────────────────────────
def test_rbac_order_isolation(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9200000133", "admin")
    _, farmer_a = make_farmer("9200000134")
    _, farmer_b = make_farmer("9200000135")
    order = checkout(client, farmer_a, ids["v1"], qty=1)
    response = client.get(f"/api/v1/store/orders/{order['id']}", headers=farmer_b)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
    listed = client.get("/api/v1/store/orders", headers=farmer_b).json()
    assert all(o["id"] != order["id"] for o in listed)
    # Staff order view is unchanged: still farmer-scoped, no backdoor.
    response = client.get(f"/api/v1/store/orders/{order['id']}", headers=staff)
    assert response.status_code == 404, response.text


# ── 21: payments intact ──────────────────────────────────────────────
def test_rbac_payments_webhook_intact(client: TestClient):
    get_settings().payment_webhook_secret = _WEBHOOK_SECRET
    ids = seed_catalog()
    _, farmer = make_farmer("9200000136")
    order = checkout(client, farmer, ids["v1"], qty=1)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "rbac-key-0001"},
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


# ── 22: khata GET-only ───────────────────────────────────────────────
def test_rbac_khata_get_only(client: TestClient):
    get_settings().payment_webhook_secret = _WEBHOOK_SECRET
    ids = seed_catalog()
    _, farmer_a = make_farmer("9200000137")
    _, farmer_b = make_farmer("9200000138")
    fake_id = str(uuid.uuid4())
    assert client.post("/api/v1/khata/entries", json={}, headers=farmer_a).status_code in (404, 405)
    assert client.put(f"/api/v1/khata/entries/{fake_id}", json={}, headers=farmer_a).status_code in (404, 405)
    assert client.delete(f"/api/v1/khata/entries/{fake_id}", headers=farmer_a).status_code in (404, 405)
    assert client.post("/api/v1/khata/summary", json={}, headers=farmer_a).status_code in (404, 405)
    # Farmer scoping: A's payment writes A's entry only; B sees none.
    order = checkout(client, farmer_a, ids["v1"], qty=1)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "rbac-khata-01"},
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


# ── 23: allowlist dead ───────────────────────────────────────────────
def test_rbac_allowlist_dead(client: TestClient):
    _, farmer = make_farmer("9200000139")
    get_settings().store_staff_mobiles = "9200000139"
    response = client.get(STAFF, headers=farmer)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"
    response = client.post(SUP, json={"name": "Allowlist Bypass"}, headers=farmer)
    assert response.status_code == 403, response.text
    ids = seed_catalog()
    response = client.post(
        f"{INV}/{ids['v1']}/adjust",
        json={"movement_type": "opening_stock", "qty": 1},
        headers=farmer,
    )
    assert response.status_code == 403, response.text


# ── 24: audit log ────────────────────────────────────────────────────
def test_rbac_audit_log_written(client: TestClient):
    admin_user, admin = make_staff("9200000140", "admin")
    target, _ = make_farmer("9200000141")
    assert audit_rows("staff_create") == []
    created = client.post(
        STAFF,
        json={"mobile_number": target.mobile_number, "role": "store_staff"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    rows = audit_rows("staff_create")
    assert len(rows) == 1
    assert rows[0].actor_user_id == admin_user.id
    assert rows[0].target_user_id == target.id
    assert rows[0].new_role == "store_staff"
    response = client.put(
        f"{STAFF}/{created.json()['id']}",
        json={"role": "store_manager"},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    rows = audit_rows("role_change")
    assert len(rows) == 1
    assert (rows[0].old_role, rows[0].new_role) == ("store_staff", "store_manager")
    assert rows[0].actor_user_id == admin_user.id
    assert rows[0].target_user_id == target.id
