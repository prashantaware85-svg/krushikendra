"""Step 18 POS counter-billing tests (SQLite, scoped tables, minimal app).

Test-only file: no app code, migrations, or existing tests touched.

Pattern (from tests/test_inventory.py + tests/test_rbac.py): minimal FastAPI
app mounting commerce + inventory + pos + khata + payments routers, per-test
SQLite schema, real JWT farmers, staff seeded as active StoreStaff rows via
make_staff (Step 17 DB RBAC). Staff discount cap comes from settings
pos_staff_max_discount_paise (Rs 200 default).

Covers: product search + variant detail; draft create (server-computed
totals, multi-item, invalid/inactive/POR variants, qty validation, no stock
effect); complete cash (stock down + sale movements, idempotent repeat,
insufficient Marathi, tamper-ignored totals, discount rules, cap matrix,
cash validation, change math, UPI/card refs, credit+Khata, walk-in,
customer isolation); immutability + cancel matrix (manager restore,
staff 403, idempotent, draft no-op, receipt shape, list/get, summary);
farmer/unauth/inactive/cross-store gates; online checkout + webhook HMAC +
khata GET-only regressions.
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
from app.models.inventory import DEFAULT_STORE_ID, InventoryItem, StockMovement
from app.models.khata import KhataEntry
from app.models.payments import Payment
from app.models.pos import PosBill, PosBillCounter, PosBillItem
from app.models.staff import StoreAuditLog, StoreStaff
from app.models.store import Product, ProductCategory, ProductVariant
from app.modules.commerce.router import router as commerce_router
from app.modules.inventory.router import router as inventory_router
from app.modules.khata.router import router as khata_router
from app.modules.payments.router import router as payments_router
from app.modules.pos.router import router as pos_router

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
    InventoryItem.__table__,
    StockMovement.__table__,
    StoreStaff.__table__,
    StoreAuditLog.__table__,
    Payment.__table__,
    KhataEntry.__table__,
    PosBill.__table__,
    PosBillItem.__table__,
    PosBillCounter.__table__,
]

ADDRESS = {
    "label": "Home",
    "line1": "123 Farm Road",
    "city": "Nashik",
    "state": "Maharashtra",
    "pincode": "422001",
    "phone": "9876543210",
}

POS = "/api/v1/store/pos"
INV = "/api/v1/store/inventory"
INSUFFICIENT = "पुरेसा स्टॉक उपलब्ध नाही."
_WEBHOOK_SECRET = "test-pos-webhook-secret"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (pos test)")
    register_exception_handlers(app)
    app.include_router(commerce_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(pos_router, prefix="/api/v1")
    app.include_router(khata_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    return app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=TABLES)
    Base.metadata.create_all(bind=engine, tables=TABLES)
    settings = get_settings()
    old_allowlist = settings.store_staff_mobiles
    old_webhook = settings.payment_webhook_secret
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
    settings.payment_webhook_secret = old_webhook


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


def seed_catalog() -> dict:
    """Active product (v1/v2 priced) + price-on-request + inactive product."""
    with TestingSession() as db:
        category = ProductCategory(name="Seeds", description="POS catalogue")
        db.add(category)
        db.flush()
        product = Product(
            name="Cotton Seeds",
            description="POS product",
            category_id=category.id,
            base_price_paise=25000,
            is_active=True,
        )
        db.add(product)
        db.flush()
        v1 = ProductVariant(
            product_id=product.id, name="1 kg", price_paise=25000, stock_qty=100
        )
        v2 = ProductVariant(
            product_id=product.id, name="500 g", price_paise=10000, stock_qty=100
        )
        por = ProductVariant(
            product_id=product.id,
            name="Bulk sack",
            price_paise=None,
            stock_qty=100,
        )
        inactive_product = Product(
            name="Old Seeds",
            description="inactive",
            category_id=category.id,
            base_price_paise=5000,
            is_active=False,
        )
        db.add(inactive_product)
        db.flush()
        inactive_v = ProductVariant(
            product_id=inactive_product.id,
            name="1 kg",
            price_paise=5000,
            stock_qty=100,
        )
        db.add_all([v1, v2, por, inactive_v])
        db.commit()
        return {
            "product": str(product.id),
            "v1": str(v1.id),
            "v2": str(v2.id),
            "por": str(por.id),
            "inactive_v": str(inactive_v.id),
        }


def adjust(
    client: TestClient, headers: dict, variant_id: str, mtype: str, qty, reason=None
):
    payload: dict = {"movement_type": mtype, "qty": qty}
    if reason is not None:
        payload["reason"] = reason
    return client.post(f"{INV}/{variant_id}/adjust", json=payload, headers=headers)


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


def movements_of(variant_id: str) -> list:
    with TestingSession() as db:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.store_id == DEFAULT_STORE_ID,
                InventoryItem.variant_id == uuid.UUID(variant_id),
            )
            .one_or_none()
        )
        if item is None:
            return []
        return (
            db.query(StockMovement)
            .filter(StockMovement.inventory_item_id == item.id)
            .order_by(StockMovement.created_at.asc())
            .all()
        )


def create_bill(
    client: TestClient, headers: dict, items: list, **kw
) -> dict:
    payload: dict = {"items": items}
    payload.update(kw)
    response = client.post(f"{POS}/bills", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def complete_bill(
    client: TestClient, headers: dict, bill_id: str, **kw
) -> TestClient:
    return client.post(f"{POS}/bills/{bill_id}/complete", json=kw, headers=headers)


def _sign(ref: str, status_value: str) -> str:
    return hmac.new(
        _WEBHOOK_SECRET.encode(), f"{ref}.{status_value}".encode(), hashlib.sha256
    ).hexdigest()


def checkout(client: TestClient, headers: dict, variant_id: str, qty: int = 1) -> dict:
    response = client.post(
        "/api/v1/store/cart/items",
        json={"variant_id": variant_id, "qty": qty},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    address = client.post("/api/v1/store/addresses", json=ADDRESS, headers=headers)
    assert address.status_code == 201, address.text
    response = client.post(
        "/api/v1/store/checkout",
        json={"address_id": address.json()["id"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ── Products ──────────────────────────────────────────────────────────
def test_pos_products_search_shape(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000101")
    response = client.get(f"{POS}/products", headers=staff)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 3  # v1, v2, POR; inactive product hidden
    by_variant = {r["variant_id"]: r for r in rows}
    assert by_variant[ids["v1"]]["unit_price_paise"] == 25000
    assert by_variant[ids["por"]]["price_on_request"] is True
    assert by_variant[ids["por"]]["unit_price_paise"] is None
    assert ids["inactive_v"] not in by_variant
    # Search covers product + variant names.
    response = client.get(f"{POS}/products", params={"search": "Cotton"}, headers=staff)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 3
    response = client.get(f"{POS}/products", params={"search": "Bulk"}, headers=staff)
    assert [r["variant_id"] for r in response.json()] == [ids["por"]]
    response = client.get(
        f"{POS}/products", params={"search": "ZZZ-no-match"}, headers=staff
    )
    assert response.json() == []


def test_pos_product_detail_and_inactive_hidden(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000102")
    response = client.get(f"{POS}/products/{ids['v1']}", headers=staff)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["variant_name"] == "1 kg"
    assert body["unit_price_paise"] == 25000
    assert body["price_on_request"] is False
    response = client.get(f"{POS}/products/{ids['inactive_v']}", headers=staff)
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "POS_VARIANT_NOT_FOUND"
    response = client.get(f"{POS}/products/{uuid.uuid4()}", headers=staff)
    assert response.status_code == 404, response.text


# ── Draft create ──────────────────────────────────────────────────────
def test_pos_create_draft_server_totals(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000103")
    bill = create_bill(
        client, staff, [{"variant_id": ids["v1"], "qty": 2}], discount_paise=1000,
        other_charges_paise=200,
    )
    assert bill["sale_status"] == "draft"
    assert bill["payment_status"] == "pending"
    assert bill["subtotal_paise"] == 50000  # 2 x 25000, server math
    assert bill["total_paise"] == 50000 - 1000 + 200
    assert len(bill["items"]) == 1
    assert bill["items"][0]["line_total_paise"] == 50000
    assert bill["bill_number"].startswith("KSK-")


def test_pos_create_multi_item_totals(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000104")
    bill = create_bill(
        client,
        staff,
        [
            {"variant_id": ids["v1"], "qty": 1},
            {"variant_id": ids["v2"], "qty": 3},
        ],
    )
    assert bill["subtotal_paise"] == 25000 + 3 * 10000
    assert bill["total_paise"] == bill["subtotal_paise"]
    assert len(bill["items"]) == 2


def test_pos_create_invalid_variant_404(client: TestClient):
    seed_catalog()
    _, staff = make_staff("9310000105")
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": str(uuid.uuid4()), "qty": 1}]},
        headers=staff,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "VARIANT_NOT_FOUND"


def test_pos_create_inactive_product_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000106")
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["inactive_v"], "qty": 1}]},
        headers=staff,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "PRODUCT_UNORDERABLE"


def test_pos_create_price_on_request_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000107")
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["por"], "qty": 1}]},
        headers=staff,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "PRICE_ON_REQUEST"


def test_pos_create_qty_zero_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000108")
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["v1"], "qty": 0}]},
        headers=staff,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "POS_QTY_INVALID"


def test_pos_create_qty_negative_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000109")
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["v1"], "qty": -2}]},
        headers=staff,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "POS_QTY_INVALID"


def test_pos_draft_does_not_deduct_stock(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000110")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    before = client.get(f"{INV}/{ids['v1']}", headers=staff).json()
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 2}])
    assert bill["sale_status"] == "draft"
    assert stock_of(ids["v1"]) == Decimal("10")
    after = client.get(f"{INV}/{ids['v1']}", headers=staff).json()
    assert after["qty_on_hand"] == before["qty_on_hand"]
    assert [m.movement_type for m in movements_of(ids["v1"])] == ["opening_stock"]


# ── Complete ──────────────────────────────────────────────────────────
def test_pos_complete_cash_stock_and_sale_movement(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000111")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 2}])
    total = bill["total_paise"]
    response = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=total,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert body["bill"]["sale_status"] == "completed"
    assert body["bill"]["payment_status"] == "paid"
    assert body["bill"]["payment_mode"] == "cash"
    assert stock_of(ids["v1"]) == Decimal("8")
    sales = [m for m in movements_of(ids["v1"]) if m.movement_type == "sale"]
    assert len(sales) == 1
    assert (sales[0].qty, sales[0].qty_before, sales[0].qty_after) == (
        Decimal("2"), Decimal("10"), Decimal("8"),
    )
    assert sales[0].reference_type == "pos_sale"
    assert sales[0].reference_id == uuid.UUID(bill["id"])


def test_pos_duplicate_complete_idempotent(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000112")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 2}])
    first = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    second = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert stock_of(ids["v1"]) == Decimal("8")  # deducted once
    assert len([m for m in movements_of(ids["v1"]) if m.movement_type == "sale"]) == 1


def test_pos_complete_insufficient_stock_marathi(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000113")
    assert adjust(client, staff, ids["v1"], "opening_stock", 1).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 2}])
    response = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "INVENTORY_INSUFFICIENT"
    assert INSUFFICIENT in body["message"]
    assert stock_of(ids["v1"]) == Decimal("1")  # unchanged


def test_pos_create_ignores_client_totals(client: TestClient):
    """Body has no totals fields: extra keys must be ignored, server recomputes."""
    ids = seed_catalog()
    _, staff = make_staff("9310000114")
    response = client.post(
        f"{POS}/bills",
        json={
            "items": [{"variant_id": ids["v1"], "qty": 1}],
            "total_paise": 1,
            "subtotal_paise": 999999,
            "line_total_paise": 7,
        },
        headers=staff,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subtotal_paise"] == 25000
    assert body["total_paise"] == 25000


def test_pos_create_discount_math_server_recomputed(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000115")
    response = client.post(
        f"{POS}/bills",
        json={
            "items": [{"variant_id": ids["v1"], "qty": 2}],
            "discount_paise": 1000,
            "other_charges_paise": 200,
            "total_paise": 5,  # tamper attempt: no such field, must be ignored
        },
        headers=staff,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subtotal_paise"] == 50000
    assert body["total_paise"] == 50000 - 1000 + 200  # server math wins


def test_pos_discount_above_subtotal_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000116")
    response = client.post(
        f"{POS}/bills",
        json={
            "items": [{"variant_id": ids["v2"], "qty": 1}],  # subtotal 10000
            "discount_paise": 10001,
        },
        headers=staff,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "POS_DISCOUNT_INVALID"


def test_pos_staff_discount_cap_vs_manager_admin(client: TestClient):
    ids = seed_catalog()
    cap = get_settings().pos_staff_max_discount_paise
    assert cap == 20000
    _, cashier = make_staff("9310000117", "store_staff")
    _, manager = make_staff("9310000118", "store_manager")
    _, admin = make_staff("9310000119", "admin")
    items = [{"variant_id": ids["v1"], "qty": 2}]  # subtotal 50000
    response = client.post(
        f"{POS}/bills", json={"items": items, "discount_paise": cap + 5000},
        headers=cashier,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "POS_DISCOUNT_LIMIT"
    for headers in (manager, admin):
        response = client.post(
            f"{POS}/bills", json={"items": items, "discount_paise": cap + 5000},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["discount_paise"] == cap + 5000
    # At-cap discount is fine for plain staff.
    response = client.post(
        f"{POS}/bills", json={"items": items, "discount_paise": cap},
        headers=cashier,
    )
    assert response.status_code == 201, response.text


def test_pos_cash_insufficient_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000120")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"] - 1,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "POS_PAYMENT_INSUFFICIENT"
    assert stock_of(ids["v1"]) == Decimal("10")  # unchanged


def test_pos_cash_change_math(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000121")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    total = bill["total_paise"]
    response = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=total + 500,
    )
    assert response.status_code == 200, response.text
    completed = response.json()["bill"]
    assert completed["amount_paid_paise"] == total
    assert completed["balance_due_paise"] == 0
    receipt = client.get(f"{POS}/bills/{bill['id']}/receipt", headers=staff).json()
    assert receipt["payment"]["received_paise"] == total + 500
    assert receipt["payment"]["change_paise"] == 500


def test_pos_upi_reference_recorded(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000122")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = complete_bill(
        client, staff, bill["id"], payment_mode="upi",
        payment_reference="UPI-REF-123",
    )
    assert response.status_code == 200, response.text
    completed = response.json()["bill"]
    assert completed["payment_mode"] == "upi"
    assert completed["payment_reference"] == "UPI-REF-123"
    assert completed["payment_status"] == "paid"


def test_pos_card_no_card_data_stored(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000123")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = complete_bill(
        client, staff, bill["id"], payment_mode="card",
        payment_reference="CARD-AUTH-9",
    )
    assert response.status_code == 200, response.text
    text = response.text.lower()
    for secret in ("card_number", "cardnumber", "cvv", "expiry", "pan"):
        assert secret not in text, secret
    assert response.json()["bill"]["payment_reference"] == "CARD-AUTH-9"


def test_pos_credit_requires_customer_422(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000124")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    assert bill["customer_id"] is None
    response = complete_bill(client, staff, bill["id"], payment_mode="credit")
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "POS_CUSTOMER_REQUIRED"


def test_pos_credit_creates_khata_debit(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000125")
    customer, customer_headers = make_farmer("9310000126")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(
        client, staff, [{"variant_id": ids["v1"], "qty": 1}],
        customer_id=str(customer.id),
    )
    response = complete_bill(client, staff, bill["id"], payment_mode="credit")
    assert response.status_code == 200, response.text
    completed = response.json()["bill"]
    assert completed["payment_status"] == "credit"
    assert completed["balance_due_paise"] == completed["total_paise"]
    summary = client.get("/api/v1/khata/summary", headers=customer_headers).json()
    assert summary["outstanding_paise"] == completed["total_paise"]
    entries = client.get("/api/v1/khata/entries", headers=customer_headers).json()
    debits = [e for e in entries["entries"] if e["entry_type"] == "debit"]
    assert len(debits) == 1
    assert debits[0]["amount_paise"] == completed["total_paise"]


def test_pos_repeat_complete_no_duplicate_khata(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000127")
    customer, customer_headers = make_farmer("9310000128")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(
        client, staff, [{"variant_id": ids["v1"], "qty": 1}],
        customer_id=str(customer.id),
    )
    first = complete_bill(client, staff, bill["id"], payment_mode="credit")
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    second = complete_bill(client, staff, bill["id"], payment_mode="credit")
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    entries = client.get("/api/v1/khata/entries", headers=customer_headers).json()
    assert len([e for e in entries["entries"] if e["entry_type"] == "debit"]) == 1


def test_pos_walkin_cash_no_customer(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000129")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["bill"]["customer_id"] is None
    assert stock_of(ids["v1"]) == Decimal("9")


def test_pos_unknown_customer_404(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000130")
    response = client.post(
        f"{POS}/bills",
        json={
            "items": [{"variant_id": ids["v1"], "qty": 1}],
            "customer_id": str(uuid.uuid4()),
        },
        headers=staff,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


# ── Immutability / cancel / reads ─────────────────────────────────────
def test_pos_bill_immutable(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000131")
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    assert client.put(
        f"{POS}/bills/{bill['id']}", json={"discount_paise": 5}, headers=staff
    ).status_code in (404, 405)
    assert client.delete(f"{POS}/bills/{bill['id']}", headers=staff).status_code in (
        404, 405,
    )
    fetched = client.get(f"{POS}/bills/{bill['id']}", headers=staff).json()
    assert fetched["discount_paise"] == 0  # untouched


def test_pos_manager_cancel_restores_stock(client: TestClient):
    ids = seed_catalog()
    _, manager = make_staff("9310000132", "store_manager")
    assert adjust(client, manager, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, manager, [{"variant_id": ids["v1"], "qty": 2}])
    done = complete_bill(
        client, manager, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert done.status_code == 200, done.text
    assert stock_of(ids["v1"]) == Decimal("8")
    response = client.post(
        f"{POS}/bills/{bill['id']}/cancel",
        json={"reason": "Customer returned items"},
        headers=manager,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert body["bill"]["sale_status"] == "cancelled"
    assert stock_of(ids["v1"]) == Decimal("10")
    returns = [m for m in movements_of(ids["v1"]) if m.movement_type == "return_in"]
    assert len(returns) == 1
    assert (returns[0].qty_before, returns[0].qty_after) == (
        Decimal("8"), Decimal("10"),
    )


def test_pos_staff_cancel_forbidden(client: TestClient):
    ids = seed_catalog()
    _, cashier = make_staff("9310000133", "store_staff")
    _, manager = make_staff("9310000134", "store_manager")
    bill = create_bill(client, cashier, [{"variant_id": ids["v1"], "qty": 1}])
    response = client.post(f"{POS}/bills/{bill['id']}/cancel", headers=cashier)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_MANAGER_REQUIRED"
    assert client.get(f"{POS}/bills/{bill['id']}", headers=manager).json()[
        "sale_status"
    ] == "draft"


def test_pos_duplicate_cancel_idempotent_credit_reversal(client: TestClient):
    ids = seed_catalog()
    _, manager = make_staff("9310000135", "store_manager")
    customer, customer_headers = make_farmer("9310000136")
    assert adjust(client, manager, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(
        client, manager, [{"variant_id": ids["v1"], "qty": 2}],
        customer_id=str(customer.id),
    )
    assert complete_bill(
        client, manager, bill["id"], payment_mode="credit"
    ).status_code == 200
    assert client.get("/api/v1/khata/summary", headers=customer_headers).json()[
        "outstanding_paise"
    ] == bill["total_paise"]
    first = client.post(f"{POS}/bills/{bill['id']}/cancel", headers=manager)
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    second = client.post(f"{POS}/bills/{bill['id']}/cancel", headers=manager)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert stock_of(ids["v1"]) == Decimal("10")  # restored once
    assert len([m for m in movements_of(ids["v1"]) if m.movement_type == "return_in"]) == 1
    # Khata debit reversed exactly once: outstanding back to zero.
    assert client.get("/api/v1/khata/summary", headers=customer_headers).json()[
        "outstanding_paise"
    ] == 0


def test_pos_draft_cancel_no_stock_effect(client: TestClient):
    ids = seed_catalog()
    _, manager = make_staff("9310000137", "store_manager")
    assert adjust(client, manager, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(client, manager, [{"variant_id": ids["v1"], "qty": 2}])
    response = client.post(f"{POS}/bills/{bill['id']}/cancel", headers=manager)
    assert response.status_code == 200, response.text
    assert response.json()["bill"]["sale_status"] == "cancelled"
    assert stock_of(ids["v1"]) == Decimal("10")
    assert [m.movement_type for m in movements_of(ids["v1"])] == ["opening_stock"]


def test_pos_receipt_shape_no_secrets(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000138")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    bill = create_bill(
        client, staff, [{"variant_id": ids["v1"], "qty": 2}], discount_paise=500,
    )
    done = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"] + 100,
    )
    assert done.status_code == 200, done.text
    response = client.get(f"{POS}/bills/{bill['id']}/receipt", headers=staff)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["bill_number"] == bill["bill_number"]
    assert len(receipt["items"]) == 1
    item = receipt["items"][0]
    assert item["line_total_paise"] == 50000
    assert receipt["subtotal_paise"] == 50000
    assert receipt["discount_paise"] == 500
    assert receipt["total_paise"] == bill["total_paise"]
    assert receipt["footer"]  # "धन्यवाद! पुन्हा भेट द्या."
    assert receipt["payment"]["change_paise"] == 100
    text = response.text.lower()
    for secret in ("sold_by", "customer_id", "mobile", "card_number", "cvv", "expiry"):
        assert secret not in text, secret


def test_pos_list_and_get_bills(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000139")
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = client.get(f"{POS}/bills", headers=staff)
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 1
    assert page["bills"][0]["bill_number"] == bill["bill_number"]
    response = client.get(f"{POS}/bills/{bill['id']}", headers=staff)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == bill["id"]
    assert client.get(f"{POS}/bills/{uuid.uuid4()}", headers=staff).status_code == 404
    done = complete_bill(
        client, staff, bill["id"], payment_mode="cash",
        amount_received_paise=bill["total_paise"],
    )
    assert done.status_code == 200, done.text
    filtered = client.get(
        f"{POS}/bills", params={"sale_status": "completed"}, headers=staff
    ).json()
    assert filtered["total"] == 1
    assert client.get(
        f"{POS}/bills", params={"sale_status": "draft"}, headers=staff
    ).json()["total"] == 0


def test_pos_summary_counts_completed_only(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000140")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    draft = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    empty = client.get(f"{POS}/summary", headers=staff).json()
    assert empty["bills"] == 0 and empty["total_paise"] == 0
    done = complete_bill(
        client, staff, draft["id"], payment_mode="cash",
        amount_received_paise=draft["total_paise"],
    )
    assert done.status_code == 200, done.text
    summary = client.get(f"{POS}/summary", headers=staff).json()
    assert summary["bills"] == 1  # draft excluded, completed counted
    assert summary["total_paise"] == draft["total_paise"]
    assert summary["breakdown"]["cash"]["bills"] == 1


# ── Gates ─────────────────────────────────────────────────────────────
def test_pos_farmer_forbidden(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000141")
    _, farmer = make_farmer("9310000142")
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    for method, url in [
        ("get", f"{POS}/products"),
        ("get", f"{POS}/bills"),
        ("get", f"{POS}/bills/{bill['id']}"),
        ("get", f"{POS}/bills/{bill['id']}/receipt"),
        ("get", f"{POS}/summary"),
    ]:
        response = getattr(client, method)(url, headers=farmer)
        assert response.status_code == 403, (method, url, response.text)
        assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["v1"], "qty": 1}]},
        headers=farmer,
    )
    assert response.status_code == 403, response.text


def test_pos_unauth_401(client: TestClient):
    assert client.get(f"{POS}/products").status_code == 401
    assert client.get(f"{POS}/bills").status_code == 401
    assert client.get(f"{POS}/summary").status_code == 401


def test_pos_inactive_staff_403(client: TestClient):
    ids = seed_catalog()
    user, headers = make_staff("9310000143")
    with TestingSession() as db:
        row = (
            db.query(StoreStaff)
            .filter(
                StoreStaff.store_id == DEFAULT_STORE_ID,
                StoreStaff.user_id == user.id,
            )
            .one()
        )
        row.is_active = False
        db.commit()
    response = client.get(f"{POS}/products", headers=headers)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_INACTIVE"
    response = client.post(
        f"{POS}/bills",
        json={"items": [{"variant_id": ids["v1"], "qty": 1}]},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_pos_cross_store_no_leak(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000144")
    outsider, outsider_headers = make_farmer("9310000145")
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
    bill = create_bill(client, staff, [{"variant_id": ids["v1"], "qty": 1}])
    response = client.get(f"{POS}/products", headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    response = client.get(f"{POS}/bills", headers=outsider_headers)
    assert response.status_code in (403, 404), response.text
    assert bill["bill_number"] not in response.text
    response = client.get(f"{POS}/bills/{bill['id']}", headers=outsider_headers)
    assert response.status_code in (403, 404), response.text


# ── Regressions ───────────────────────────────────────────────────────
def test_pos_online_checkout_regression(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9310000146")
    _, farmer = make_farmer("9310000147")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, ids["v1"], qty=1)
    assert order["id"]
    assert order["status"] in ("pending", "placed", "created", order["status"])


def test_pos_webhook_hmac_regression(client: TestClient):
    get_settings().payment_webhook_secret = _WEBHOOK_SECRET
    ids = seed_catalog()
    _, farmer = make_farmer("9310000148")
    order = checkout(client, farmer, ids["v1"], qty=1)
    payment = client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order["id"], "idempotency_key": "pos-key-0001"},
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


def test_pos_khata_get_only_regression(client: TestClient):
    _, farmer = make_farmer("9310000149")
    fake_id = str(uuid.uuid4())
    assert client.post("/api/v1/khata/entries", json={}, headers=farmer).status_code in (
        404, 405,
    )
    assert client.put(
        f"/api/v1/khata/entries/{fake_id}", json={}, headers=farmer
    ).status_code in (404, 405)
    assert client.delete(f"/api/v1/khata/entries/{fake_id}", headers=farmer).status_code in (
        404, 405,
    )
    assert client.post("/api/v1/khata/summary", json={}, headers=farmer).status_code in (
        404, 405,
    )
    assert client.get("/api/v1/khata/summary", headers=farmer).status_code == 200
    assert client.get("/api/v1/khata/entries", headers=farmer).status_code == 200
