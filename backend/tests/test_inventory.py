"""Step 16 inventory tests (SQLite, scoped tables, minimal app).

Covers: supplier CRUD + staff gate; purchase draft/add-items/server totals +
receive/cancel transitions; manual adjustments (opening/in/out/damaged/
expired/return); order-confirm sale hook + cancel restoration (service-level
transitions, no admin route exists); low/out detection; farmer-safe reads;
movement immutability; auth gates. Test-only file: no app code touched.

Pattern: minimal FastAPI app (commerce + suppliers + purchases + inventory
routers), per-test SQLite schema, real JWT farmer, staff via
StoreStaff rows (Step 17 DB RBAC).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
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
from app.models.inventory import (
    DEFAULT_STORE_ID,
    InventoryItem,
    StockMovement,
)
from app.models.staff import StoreAuditLog, StoreStaff
from app.models.store import Product, ProductCategory, ProductVariant
from app.models.inventory import Purchase, PurchaseItem, Supplier
from app.modules.commerce import service as commerce_service
from app.modules.commerce.router import router as commerce_router
from app.modules.inventory import service as inventory_service
from app.modules.inventory.router import router as inventory_router
from app.modules.purchases.router import router as purchases_router
from app.modules.suppliers.router import router as suppliers_router

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
    Supplier.__table__,
    Purchase.__table__,
    PurchaseItem.__table__,
    InventoryItem.__table__,
    StockMovement.__table__,
    StoreStaff.__table__,
    StoreAuditLog.__table__,
]

ADDRESS = {
    "label": "Home",
    "line1": "123 Farm Road",
    "city": "Nashik",
    "state": "Maharashtra",
    "pincode": "422001",
    "phone": "9876543210",
}

INSUFFICIENT = "पुरेसा स्टॉक उपलब्ध नाही."
INV = "/api/v1/store/inventory"
SUP = "/api/v1/store/suppliers"
PUR = "/api/v1/store/purchases"


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (inventory test)")
    register_exception_handlers(app)
    app.include_router(commerce_router, prefix="/api/v1")
    app.include_router(suppliers_router, prefix="/api/v1")
    app.include_router(purchases_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    return app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=TABLES)
    Base.metadata.create_all(bind=engine, tables=TABLES)
    get_settings().store_staff_mobiles = ""
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
    get_settings().store_staff_mobiles = ""


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
    with TestingSession() as db:
        category = ProductCategory(name="Seeds", description="Test catalogue")
        db.add(category)
        db.flush()
        product = Product(
            name="Cotton Seeds",
            description="Test product",
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
        db.add_all([v1, v2])
        db.commit()
        return {"product": str(product.id), "v1": str(v1.id), "v2": str(v2.id)}


def make_address(client: TestClient, headers: dict) -> dict:
    response = client.post("/api/v1/store/addresses", json=ADDRESS, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def checkout(client: TestClient, headers: dict, lines: dict[str, int]) -> dict:
    for variant_id, qty in lines.items():
        response = client.post(
            "/api/v1/store/cart/items",
            json={"variant_id": variant_id, "qty": qty},
            headers=headers,
        )
        assert response.status_code == 201, response.text
    address = make_address(client, headers)
    response = client.post(
        "/api/v1/store/checkout", json={"address_id": address["id"]}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_order(order_id: str) -> None:
    with TestingSession() as db:
        order = db.get(Order, uuid.UUID(order_id))
        assert order is not None
        commerce_service.transition_order(db, order, "confirmed")


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


def adjust(
    client: TestClient, headers: dict, variant_id: str, mtype: str, qty, reason=None
):
    payload: dict = {"movement_type": mtype, "qty": qty}
    if reason is not None:
        payload["reason"] = reason
    return client.post(f"{INV}/{variant_id}/adjust", json=payload, headers=headers)


# ── Suppliers ─────────────────────────────────────────────────────────
def test_supplier_crud_staff(client: TestClient):
    _, staff = make_staff("9000000101")
    response = client.post(f"{SUP}", json={"name": "Agro Traders"}, headers=staff)
    assert response.status_code == 201, response.text
    supplier = response.json()
    assert supplier["name"] == "Agro Traders"

    response = client.get(f"{SUP}/{supplier['id']}", headers=staff)
    assert response.status_code == 200, response.text

    response = client.put(
        f"{SUP}/{supplier['id']}", json={"name": "Agro Traders Ltd"}, headers=staff
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Agro Traders Ltd"

    response = client.get(f"{SUP}", headers=staff)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1


def test_supplier_farmer_forbidden(client: TestClient):
    _, staff = make_staff("9000000102")
    _, farmer = make_farmer("9000000103")
    created = client.post(f"{SUP}", json={"name": "Agro"}, headers=staff).json()
    for method, url, payload in [
        ("get", f"{SUP}", None),
        ("post", f"{SUP}", {"name": "X"}),
        ("get", f"{SUP}/{created['id']}", None),
        ("put", f"{SUP}/{created['id']}", {"name": "Y"}),
    ]:
        response = getattr(client, method)(url, headers=farmer, json=payload) if payload else getattr(client, method)(url, headers=farmer)
        assert response.status_code == 403, (method, url, response.text)
        assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"


def test_supplier_cross_staff_visibility(client: TestClient):
    _, staff_a = make_staff("9000000104")
    _, staff_b = make_staff("9000000105")
    response = client.post(f"{SUP}", json={"name": "Shared Supplier"}, headers=staff_a)
    assert response.status_code == 201, response.text
    response = client.get(f"{SUP}", headers=staff_b)
    assert response.status_code == 200, response.text
    assert [s["name"] for s in response.json()["suppliers"]] == ["Shared Supplier"]


def test_supplier_blank_name_rejected(client: TestClient):
    _, staff = make_staff("9000000106")
    response = client.post(f"{SUP}", json={"name": "   "}, headers=staff)
    assert response.status_code == 422, response.text


# ── Purchases ─────────────────────────────────────────────────────────
def test_purchase_draft_create_defaults(client: TestClient):
    _, staff = make_staff("9000000111")
    response = client.post(f"{PUR}", json={}, headers=staff)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["subtotal_paise"] == 0 and body["total_paise"] == 0
    assert body["purchase_number"].startswith("PO-")


def test_purchase_items_server_totals_tamper_ignored(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000112")
    # Client totals are not even schema fields: extra keys must be ignored.
    response = client.post(
        f"{PUR}",
        json={"total_paise": 1, "subtotal_paise": 999999},
        headers=staff,
    )
    assert response.status_code == 201, response.text
    purchase = response.json()
    assert purchase["subtotal_paise"] == 0 and purchase["total_paise"] == 0

    response = client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 2, "unit_cost_paise": 5000},
        headers=staff,
    )
    assert response.status_code == 201, response.text
    assert response.json()["line_total_paise"] == 10000  # 2 × 5000, server math

    body = client.get(f"{PUR}/{purchase['id']}", headers=staff).json()
    assert body["subtotal_paise"] == 10000 and body["total_paise"] == 10000

    response = client.put(
        f"{PUR}/{purchase['id']}",
        json={"discount_paise": 1500, "other_charges_paise": 500},
        headers=staff,
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_paise"] == 9000  # 10000 − 1500 + 500


def test_purchase_receive_increases_stock(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000113")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 7, "unit_cost_paise": 4000},
        headers=staff,
    )
    response = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "received" and body["duplicate"] is False
    assert stock_of(ids["v1"]) == Decimal("7")
    rows = movements_of(ids["v1"])
    assert len(rows) == 1
    assert rows[0].movement_type == "purchase"
    assert (rows[0].qty_before, rows[0].qty_after) == (Decimal("0"), Decimal("7"))
    assert rows[0].reference_type == "purchase_receipt"


def test_purchase_two_variants_two_movements(client: TestClient):
    """Regression: uq_stock_move_ref_type is per-line (one row per variant)."""
    ids = seed_catalog()
    _, staff = make_staff("9000000114")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    for vid, qty in [(ids["v1"], 3), (ids["v2"], 5)]:
        response = client.post(
            f"{PUR}/{purchase['id']}/items",
            json={"variant_id": vid, "qty": qty, "unit_cost_paise": 1000},
            headers=staff,
        )
        assert response.status_code == 201, response.text
    response = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    assert response.status_code == 200, response.text
    assert stock_of(ids["v1"]) == Decimal("3")
    assert stock_of(ids["v2"]) == Decimal("5")
    assert len(movements_of(ids["v1"])) == 1
    assert len(movements_of(ids["v2"])) == 1


def test_purchase_receive_twice_idempotent(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000115")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 4, "unit_cost_paise": 1000},
        headers=staff,
    )
    first = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff).json()
    assert first["duplicate"] is False
    second = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    assert stock_of(ids["v1"]) == Decimal("4")
    assert len(movements_of(ids["v1"])) == 1


def test_purchase_cancelled_no_stock(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000116")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 4, "unit_cost_paise": 1000},
        headers=staff,
    )
    response = client.post(f"{PUR}/{purchase['id']}/cancel", headers=staff)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    response = client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    assert response.status_code == 422, response.text
    assert stock_of(ids["v1"]) is None  # no inventory row ever created


def test_purchase_edit_after_receive_rejected(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000117")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v1"], "qty": 2, "unit_cost_paise": 1000},
        headers=staff,
    )
    client.post(f"{PUR}/{purchase['id']}/receive", headers=staff)
    response = client.put(
        f"{PUR}/{purchase['id']}", json={"discount_paise": 10}, headers=staff
    )
    assert response.status_code == 422, response.text
    response = client.post(
        f"{PUR}/{purchase['id']}/items",
        json={"variant_id": ids["v2"], "qty": 1, "unit_cost_paise": 1000},
        headers=staff,
    )
    assert response.status_code == 422, response.text
    response = client.post(f"{PUR}/{purchase['id']}/cancel", headers=staff)
    assert response.status_code == 422, response.text


def test_purchase_item_qty_cost_validation(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000118")
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    for bad in [
        {"variant_id": ids["v1"], "qty": 0, "unit_cost_paise": 100},
        {"variant_id": ids["v1"], "qty": -2, "unit_cost_paise": 100},
        {"variant_id": ids["v1"], "qty": 2, "unit_cost_paise": -50},
    ]:
        response = client.post(f"{PUR}/{purchase['id']}/items", json=bad, headers=staff)
        assert response.status_code == 422, (bad, response.text)


# ── Manual adjustments ────────────────────────────────────────────────
def test_opening_stock_creates_item(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000121")
    response = adjust(client, staff, ids["v1"], "opening_stock", 50)
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(str(body["qty_on_hand"])) == Decimal("50")
    assert Decimal(str(body["available"])) == Decimal("50")
    rows = movements_of(ids["v1"])
    assert len(rows) == 1
    assert rows[0].movement_type == "opening_stock"
    assert (rows[0].qty_before, rows[0].qty_after) == (Decimal("0"), Decimal("50"))


def test_one_row_per_variant_store(client: TestClient):
    """Second opening_stock accumulates on the same row; a raw duplicate
    insert violates uq_inventory_items_store_id_variant_id."""
    ids = seed_catalog()
    _, staff = make_staff("9000000122")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    with TestingSession() as db:
        count = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.store_id == DEFAULT_STORE_ID,
                InventoryItem.variant_id == uuid.UUID(ids["v1"]),
            )
            .count()
        )
    assert count == 1
    assert stock_of(ids["v1"]) == Decimal("15")
    with TestingSession() as db:
        db.add(
            InventoryItem(
                store_id=DEFAULT_STORE_ID,
                variant_id=uuid.UUID(ids["v1"]),
                qty_on_hand=Decimal("1"),
                qty_reserved=Decimal("0"),
                reorder_level=Decimal("0"),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:  # pragma: no cover - constraint must hold
            db.rollback()
            raise AssertionError("duplicate (store, variant) insert must fail")


def test_adjust_in_and_out(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000123")
    assert adjust(client, staff, ids["v1"], "opening_stock", 20).status_code == 200
    response = adjust(client, staff, ids["v1"], "adjustment_in", 10, reason="Recount found extra")
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["qty_on_hand"])) == Decimal("30")
    response = adjust(client, staff, ids["v1"], "adjustment_out", 8, reason="Shop use")
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["qty_on_hand"])) == Decimal("22")


def test_adjust_out_insufficient_marathi(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000124")
    assert adjust(client, staff, ids["v1"], "opening_stock", 3).status_code == 200
    response = adjust(client, staff, ids["v1"], "adjustment_out", 5, reason="Too much")
    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "INVENTORY_INSUFFICIENT"
    assert INSUFFICIENT in body["message"]
    assert stock_of(ids["v1"]) == Decimal("3")  # unchanged


def test_adjust_zero_negative_qty_rejected(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000125")
    for qty in [0, -5]:
        response = adjust(client, staff, ids["v1"], "opening_stock", qty)
        assert response.status_code == 422, (qty, response.text)


def test_damaged_expired_reason_required(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000126")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    for mtype in ("damaged_out", "expired_out"):
        response = adjust(client, staff, ids["v1"], mtype, 2)
        assert response.status_code == 422, (mtype, response.text)
        assert response.json()["error"]["code"] == "INVENTORY_REASON_REQUIRED"
        response = adjust(client, staff, ids["v1"], mtype, 2, reason="Spoiled in rain")
        assert response.status_code == 200, (mtype, response.text)
    assert stock_of(ids["v1"]) == Decimal("6")


def test_adjust_return_in_no_reason_needed(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000127")
    response = adjust(client, staff, ids["v1"], "return_in", 4)
    assert response.status_code == 200, response.text
    assert stock_of(ids["v1"]) == Decimal("4")
    rows = movements_of(ids["v1"])
    assert rows[-1].movement_type == "return_in"


def test_movement_history_before_after(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000128")
    adjust(client, staff, ids["v1"], "opening_stock", 50)
    adjust(client, staff, ids["v1"], "adjustment_in", 10, reason="Found extra")
    adjust(client, staff, ids["v1"], "adjustment_out", 5, reason="Shop use")
    response = client.get(f"{INV}/{ids['v1']}/movements", headers=staff)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    # API lists newest-first; assert per-type snapshots order-free.
    by_type = {m["movement_type"]: m for m in body["movements"]}
    assert set(by_type) == {"opening_stock", "adjustment_in", "adjustment_out"}
    assert [
        (Decimal(str(by_type[t]["qty_before"])), Decimal(str(by_type[t]["qty_after"])))
        for t in ("opening_stock", "adjustment_in", "adjustment_out")
    ] == [(Decimal("0"), Decimal("50")), (Decimal("50"), Decimal("60")), (Decimal("60"), Decimal("55"))]


def test_system_movements_rejected_on_adjust(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000129")
    for mtype in ("sale", "purchase"):
        response = adjust(client, staff, ids["v1"], mtype, 1, reason="Manual")
        assert response.status_code == 422, (mtype, response.text)
        assert response.json()["error"]["code"] == "INVENTORY_MOVEMENT_INVALID"


def test_adjustment_in_out_require_reason_opening_does_not(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000130")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    assert adjust(client, staff, ids["v1"], "adjustment_in", 2).status_code == 422
    assert adjust(client, staff, ids["v1"], "adjustment_out", 2).status_code == 422


# ── Order integration (service-driven confirm; no admin route) ───────
def test_order_confirm_creates_sale(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000131")
    _, farmer = make_farmer("9000000132")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2})
    confirm_order(order["id"])
    assert stock_of(ids["v1"]) == Decimal("8")
    rows = [m for m in movements_of(ids["v1"]) if m.movement_type == "sale"]
    assert len(rows) == 1
    assert (rows[0].qty, rows[0].qty_before, rows[0].qty_after) == (
        Decimal("2"),
        Decimal("10"),
        Decimal("8"),
    )
    assert rows[0].reference_type == "order_sale"
    assert rows[0].reference_id == uuid.UUID(order["id"])


def test_order_two_lines_two_sales(client: TestClient):
    """Regression: multi-line orders write one sale row per line."""
    ids = seed_catalog()
    _, staff = make_staff("9000000133")
    _, farmer = make_farmer("9000000134")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    assert adjust(client, staff, ids["v2"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2, ids["v2"]: 3})
    confirm_order(order["id"])
    assert stock_of(ids["v1"]) == Decimal("8")
    assert stock_of(ids["v2"]) == Decimal("7")
    sales1 = [m for m in movements_of(ids["v1"]) if m.movement_type == "sale"]
    sales2 = [m for m in movements_of(ids["v2"]) if m.movement_type == "sale"]
    assert len(sales1) == 1 and len(sales2) == 1
    assert sales1[0].qty == Decimal("2") and sales2[0].qty == Decimal("3")


def test_order_second_confirm_no_duplicate_sale(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000135")
    _, farmer = make_farmer("9000000136")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2})
    confirm_order(order["id"])
    with TestingSession() as db:
        orm_order = db.get(Order, uuid.UUID(order["id"]))
        assert inventory_service.record_order_sale(db, orm_order, commit=True) is True
        assert inventory_service.record_order_sale(db, orm_order, commit=True) is True
    assert stock_of(ids["v1"]) == Decimal("8")
    assert len([m for m in movements_of(ids["v1"]) if m.movement_type == "sale"]) == 1


def test_order_cancel_after_confirm_restores_once(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000137")
    _, farmer = make_farmer("9000000138")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2})
    confirm_order(order["id"])
    response = client.post(f"/api/v1/store/orders/{order['id']}/cancel", headers=farmer)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert stock_of(ids["v1"]) == Decimal("10")
    returns = [m for m in movements_of(ids["v1"]) if m.movement_type == "return_in"]
    assert len(returns) == 1
    assert returns[0].reference_type == "order_sale"
    assert returns[0].reference_id == uuid.UUID(order["id"])
    with TestingSession() as db:
        orm_order = db.get(Order, uuid.UUID(order["id"]))
        assert inventory_service.reverse_order_sale(db, orm_order, commit=True) is True
    assert len([m for m in movements_of(ids["v1"]) if m.movement_type == "return_in"]) == 1


def test_order_cancel_pending_no_restoration(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000139")
    _, farmer = make_farmer("9000000140")
    assert adjust(client, staff, ids["v1"], "opening_stock", 10).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2})
    response = client.post(f"/api/v1/store/orders/{order['id']}/cancel", headers=farmer)
    assert response.status_code == 200, response.text
    assert stock_of(ids["v1"]) == Decimal("10")
    assert [m.movement_type for m in movements_of(ids["v1"])] == ["opening_stock"]


def test_order_confirm_insufficient_stock_marathi(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000141")
    _, farmer = make_farmer("9000000142")
    assert adjust(client, staff, ids["v1"], "opening_stock", 1).status_code == 200
    order = checkout(client, farmer, {ids["v1"]: 2})  # legacy stock_qty=100 passes
    with TestingSession() as db:
        orm_order = db.get(Order, uuid.UUID(order["id"]))
        try:
            commerce_service.transition_order(db, orm_order, "confirmed")
        except Exception as exc:
            assert INSUFFICIENT in str(exc), str(exc)
            db.rollback()
        else:  # pragma: no cover - must fail on tracked low stock
            raise AssertionError("confirm must fail on insufficient tracked stock")
    assert stock_of(ids["v1"]) == Decimal("1")  # unchanged


# ── Reads / permissions ──────────────────────────────────────────────
def test_farmer_write_endpoints_forbidden(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000151")
    _, farmer = make_farmer("9000000152")
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    purchase = client.post(f"{PUR}", json={}, headers=staff).json()
    assert adjust(client, farmer, ids["v1"], "adjustment_in", 1, reason="x").status_code == 403
    assert client.post(f"{PUR}", json={}, headers=farmer).status_code == 403
    assert client.post(f"{PUR}/{purchase['id']}/receive", headers=farmer).status_code == 403
    assert client.post(f"{SUP}", json={"name": "X"}, headers=farmer).status_code == 403


def test_farmer_movements_forbidden(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000153")
    _, farmer = make_farmer("9000000154")
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    response = client.get(f"{INV}/{ids['v1']}/movements", headers=farmer)
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "STORE_STAFF_REQUIRED"


def test_farmer_availability_without_cost(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000155")
    _, farmer = make_farmer("9000000156")
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    response = client.get(f"{INV}", headers=farmer)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    response = client.get(f"{INV}/{ids['v1']}", headers=farmer)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] == "5.000" or Decimal(str(body["available"])) == Decimal("5")
    assert body["status"] == "in"
    for hidden in ("qty_on_hand", "qty_reserved", "reorder_level", "reorder_qty", "unit_cost", "cost"):
        assert hidden not in body, hidden
    # Staff see the internal levels on the same path.
    detail = client.get(f"{INV}/{ids['v1']}", headers=staff).json()
    assert "qty_on_hand" in detail


def test_low_stock_out_detection(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000157")
    assert adjust(client, staff, ids["v1"], "opening_stock", 20).status_code == 200
    assert adjust(client, staff, ids["v2"], "opening_stock", 4).status_code == 200
    with TestingSession() as db:
        for vid, level in [(ids["v1"], "10"), (ids["v2"], "10")]:
            row = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.store_id == DEFAULT_STORE_ID,
                    InventoryItem.variant_id == uuid.UUID(vid),
                )
                .one()
            )
            row.reorder_level = Decimal(level)
        db.commit()
    response = client.get(f"{INV}", headers=staff)
    statuses = {i["variant_id"]: i["status"] for i in response.json()["items"]}
    assert statuses[ids["v1"]] == "in" and statuses[ids["v2"]] == "low"
    response = client.get(f"{INV}?status=low", headers=staff)
    assert [i["variant_id"] for i in response.json()["items"]] == [ids["v2"]]
    response = client.get(f"{INV}/low-stock", headers=staff)
    assert response.status_code == 200, response.text
    assert [i["variant_id"] for i in response.json()["items"]] == [ids["v2"]]
    summary = client.get(f"{INV}/summary", headers=staff).json()
    assert (summary["in_stock"], summary["low_stock"], summary["out_of_stock"]) == (1, 1, 0)
    # Drain v2 to zero → out-of-stock.
    assert adjust(client, staff, ids["v2"], "adjustment_out", 4, reason="Sold offline").status_code == 200
    detail = client.get(f"{INV}/{ids['v2']}", headers=staff).json()
    assert detail["status"] == "out"
    summary = client.get(f"{INV}/summary", headers=staff).json()
    assert summary["out_of_stock"] == 1


def test_movement_immutable_no_routes(client: TestClient):
    ids = seed_catalog()
    _, staff = make_staff("9000000158")
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    for method in ("put", "delete", "patch"):
        response = getattr(client, method)(f"{INV}/{ids['v1']}/movements", headers=staff)
        assert response.status_code in (404, 405), (method, response.status_code)


def test_inventory_summary_counts(client: TestClient):
    _, staff = make_staff("9000000159")
    summary = client.get(f"{INV}/summary", headers=staff).json()
    assert summary["total"] == 0 and summary["recent_movements"] == []
    ids = seed_catalog()
    assert adjust(client, staff, ids["v1"], "opening_stock", 5).status_code == 200
    summary = client.get(f"{INV}/summary", headers=staff).json()
    assert summary["total"] == 1 and summary["in_stock"] == 1
    assert len(summary["recent_movements"]) == 1


def test_unauthenticated_inventory_rejected(client: TestClient):
    response = client.get(f"{INV}")
    assert response.status_code == 401, response.text
