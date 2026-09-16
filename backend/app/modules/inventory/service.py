"""Inventory policy: availability reads + guarded adjustments + order hook.

Conventions:
- ``available = qty_on_hand − qty_reserved`` is computed on every read;
  status: ``out`` (available ≤ 0), ``low`` (available ≤ reorder_level),
  else ``in``.
- Every stock change writes one immutable ``StockMovement`` row in the SAME
  transaction (khata-style: no edit/delete of movements anywhere).
- ``ProductVariant.stock_qty`` (catalogue display) is never read or written.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from decimal import Decimal

from fastapi import status
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import User
from app.models.commerce import Order
from app.models.inventory import (
    DEFAULT_STORE_ID,
    STOCK_MOVEMENT_TYPES,
    InventoryItem,
    StockMovement,
)
from app.modules.inventory import repository
from app.modules.inventory.schemas import (
    ADJUST_IN_TYPES,
    ADJUST_TYPES,
    REASON_REQUIRED_TYPES,
    AdjustIn,
    InventoryDetailOut,
    InventoryOut,
    InventoryPage,
    InventorySummaryOut,
    MovementOut,
    MovementPage,
    ReorderLevelIn,
)

INSUFFICIENT_MESSAGE = "पुरेसा स्टॉक उपलब्ध नाही."


def _unprocessable(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def _not_found(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


def _available(item: InventoryItem) -> Decimal:
    return item.qty_on_hand - item.qty_reserved


def _status_for(item: InventoryItem) -> str:
    available = _available(item)
    if available <= 0:
        return "out"
    if available <= item.reorder_level:
        return "low"
    return "in"


def _is_missing_table(exc: DBAPIError) -> bool:
    """True when the DB error is just "Step 16 tables absent".

    Legacy/scoped databases (Steps 1–15 suites) create only their own tables.
    Probing them with ``has_table`` on the request's own connection is NOT an
    option (it silently discards that connection's pending transaction on
    SQLite) — instead the hook runs inside a SAVEPOINT and treats a
    missing-table failure as "inventory not installed → no-op", leaving the
    outer commerce transaction untouched.
    """
    message = str(exc).lower()
    return (
        "no such table" in message  # sqlite
        or "undefined table" in message  # postgres
        or ("does not exist" in message and "relation" in message)  # postgres
    )


def _base_out(item: InventoryItem, enrich: dict) -> dict:
    info = enrich.get(item.variant_id, {})
    return {
        "variant_id": item.variant_id,
        "variant_name": info.get("variant_name"),
        "product_id": info.get("product_id"),
        "product_name": info.get("product_name"),
        "category_id": info.get("category_id"),
        "available": _available(item),
        "status": _status_for(item),
    }


def _detail_out(item: InventoryItem, enrich: dict) -> InventoryDetailOut:
    return InventoryDetailOut(
        **_base_out(item, enrich),
        qty_on_hand=item.qty_on_hand,
        qty_reserved=item.qty_reserved,
        reorder_level=item.reorder_level,
        reorder_qty=item.reorder_qty,
        is_active=item.is_active,
    )


def _movement_out(row: StockMovement) -> MovementOut:
    return MovementOut.model_validate(row)


# ── Reads ─────────────────────────────────────────────────────────────
def list_inventory(
    db: Session,
    *,
    product_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    variant_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> InventoryPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if status_filter is not None and status_filter not in ("in", "low", "out"):
        raise _unprocessable("INVENTORY_STATUS_INVALID", "status must be one of in/low/out.")
    allowed: set[uuid.UUID] | None = None
    if variant_id is not None:
        allowed = {variant_id}
    if product_id is not None:
        allowed = set(repository.variant_ids_for_product(db, product_id))
    if category_id is not None:
        allowed = set(repository.variant_ids_for_category(db, category_id))
    rows = repository.list_all(db, DEFAULT_STORE_ID)
    if allowed is not None:
        rows = [r for r in rows if r.variant_id in allowed]
    enrich = repository.catalogue_map(db, {r.variant_id for r in rows})
    outs = [
        InventoryOut(**_base_out(r, enrich))
        for r in rows
        if status_filter is None or _status_for(r) == status_filter
    ]
    return InventoryPage(items=outs[offset : offset + limit], total=len(outs), limit=limit, offset=offset)


def get_summary(db: Session) -> InventorySummaryOut:
    rows = repository.list_all(db, DEFAULT_STORE_ID)
    counts = {"in": 0, "low": 0, "out": 0}
    for row in rows:
        counts[_status_for(row)] += 1
    return InventorySummaryOut(
        total=len(rows),
        in_stock=counts["in"],
        low_stock=counts["low"],
        out_of_stock=counts["out"],
        recent_movements=[
            _movement_out(m) for m in repository.recent_movements(db, DEFAULT_STORE_ID, limit=10)
        ],
    )


def get_low_stock(db: Session, *, limit: int = 20, offset: int = 0) -> InventoryPage:
    """available ≤ reorder_level; out-of-stock first, then lowest pct of reorder."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    rows = [
        r
        for r in repository.list_all(db, DEFAULT_STORE_ID)
        if _available(r) <= r.reorder_level
    ]

    def _sort_key(row: InventoryItem) -> tuple[int, Decimal]:
        available = _available(row)
        if available <= 0:
            return (0, Decimal("0"))
        pct = available / row.reorder_level if row.reorder_level > 0 else Decimal("1")
        return (1, pct)

    rows.sort(key=_sort_key)
    enrich = repository.catalogue_map(db, {r.variant_id for r in rows})
    outs = [InventoryOut(**_base_out(r, enrich)) for r in rows]
    return InventoryPage(items=outs[offset : offset + limit], total=len(outs), limit=limit, offset=offset)


def get_detail(db: Session, variant_id: uuid.UUID, *, include_internal: bool) -> InventoryOut:
    item = repository.get_item(db, DEFAULT_STORE_ID, variant_id)
    if item is None:
        raise _not_found("INVENTORY_NOT_FOUND", "No inventory record for this variant.")
    enrich = repository.catalogue_map(db, {variant_id})
    if include_internal:
        return _detail_out(item, enrich)
    return InventoryOut(**_base_out(item, enrich))


def list_movements(
    db: Session,
    variant_id: uuid.UUID,
    *,
    movement_type: str | None = None,
    date_from=None,
    date_to=None,
    limit: int = 20,
    offset: int = 0,
) -> MovementPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if movement_type is not None and movement_type not in STOCK_MOVEMENT_TYPES:
        raise _unprocessable(
            "INVENTORY_MOVEMENT_INVALID",
            f"movement_type must be one of {STOCK_MOVEMENT_TYPES}.",
        )
    item = repository.get_item(db, DEFAULT_STORE_ID, variant_id)
    if item is None:
        raise _not_found("INVENTORY_NOT_FOUND", "No inventory record for this variant.")
    since = datetime.combine(date_from, time.min) if date_from else None
    until = datetime.combine(date_to, time.min) if date_to else None
    if until is not None:  # inclusive end date
        from datetime import timedelta

        until = until + timedelta(days=1)
    rows = repository.list_movements(
        db, item.id, movement_type=movement_type, since=since, until=until,
        limit=limit, offset=offset,
    )
    return MovementPage(
        movements=[_movement_out(m) for m in rows],
        total=repository.count_movements(
            db, item.id, movement_type=movement_type, since=since, until=until
        ),
        limit=limit,
        offset=offset,
    )


# ── Manual adjustment (staff-only upstream) ───────────────────────────
def adjust_stock(
    db: Session, user: User, variant_id: uuid.UUID, payload: AdjustIn
) -> InventoryDetailOut:
    movement_type = payload.movement_type
    if movement_type in ("sale", "purchase"):
        raise _unprocessable(
            "INVENTORY_MOVEMENT_INVALID",
            "sale/purchase movements are system-owned (orders/purchases only).",
        )
    if movement_type not in ADJUST_TYPES:
        raise _unprocessable(
            "INVENTORY_MOVEMENT_INVALID",
            f"movement_type must be one of {ADJUST_TYPES}.",
        )
    if movement_type in REASON_REQUIRED_TYPES and not (payload.reason or "").strip():
        raise _unprocessable(
            "INVENTORY_REASON_REQUIRED",
            "reason is required for this movement type.",
        )
    is_in = movement_type in ADJUST_IN_TYPES
    try:
        if is_in:
            item = repository.get_or_create_item(db, DEFAULT_STORE_ID, variant_id)
        else:
            item = repository.get_item(db, DEFAULT_STORE_ID, variant_id)
            if item is None or _available(item) < payload.qty:
                raise _unprocessable("INVENTORY_INSUFFICIENT", INSUFFICIENT_MESSAGE)
        before = item.qty_on_hand
        after = before + payload.qty if is_in else before - payload.qty
        item.qty_on_hand = after
        db.add(
            StockMovement(
                store_id=DEFAULT_STORE_ID,
                inventory_item_id=item.id,
                variant_id=variant_id,
                movement_type=movement_type,
                qty=payload.qty,
                qty_before=before,
                qty_after=after,
                reference_type=None,
                reference_id=None,
                reason=(payload.reason or "").strip() or None,
                created_by=user.id,
            )
        )
        db.commit()
    except AppError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _unprocessable("INVENTORY_INSUFFICIENT", INSUFFICIENT_MESSAGE) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(item)
    return _detail_out(item, repository.catalogue_map(db, {variant_id}))


# ── Reorder tuning (manager-only upstream) ────────────────────────────
def set_reorder_level(
    db: Session, variant_id: uuid.UUID, payload: ReorderLevelIn
) -> InventoryDetailOut:
    """Set reorder_level / reorder_qty for a tracked variant (404 when untracked)."""
    item = repository.get_item(db, DEFAULT_STORE_ID, variant_id)
    if item is None:
        raise _not_found("INVENTORY_NOT_FOUND", "No inventory record for this variant.")
    item.reorder_level = payload.reorder_level
    item.reorder_qty = payload.reorder_quantity
    db.commit()
    db.refresh(item)
    return _detail_out(item, repository.catalogue_map(db, {variant_id}))


# ── Order integration (called ONLY from the commerce transition hook) ──
def _record_sale_inner(db: Session, order: Order) -> bool:
    """Inner sale work (runs inside a SAVEPOINT; no commit/rollback here)."""
    lines = [
        i for i in repository.list_order_items(db, order.id) if i.variant_id is not None
    ]
    if not lines:
        return False
    if repository.list_sale_movements(db, DEFAULT_STORE_ID, order.id):
        return True
    for line in lines:
        qty = Decimal(line.qty)
        if qty <= 0:
            continue
        item = repository.get_item(db, DEFAULT_STORE_ID, line.variant_id)
        if item is None:
            continue  # untracked variant: no stock governance yet
        if _available(item) < qty:
            raise _unprocessable("INVENTORY_INSUFFICIENT", INSUFFICIENT_MESSAGE)
        before = item.qty_on_hand
        after = before - qty
        item.qty_on_hand = after
        db.add(
            StockMovement(
                store_id=DEFAULT_STORE_ID,
                inventory_item_id=item.id,
                variant_id=line.variant_id,
                movement_type="sale",
                qty=qty,
                qty_before=before,
                qty_after=after,
                reference_type="order_sale",
                reference_id=order.id,
                reason=None,
                created_by=order.farmer_user_id,
            )
        )
    db.flush()
    return False


def record_order_sale(db: Session, order: Order, *, commit: bool = False) -> bool:
    """Decrement stock for a confirmed order (same transaction, no auto-create).

    Returns True when the sale was already recorded (idempotent no-op).
    Variants with no inventory row are SKIPPED (untracked → legacy catalogue
    display stays the source of truth), so pre-stock Step 14 confirm flows
    behave exactly as before; tracked variants validate available ≥ qty.
    """
    try:
        with db.begin_nested():
            duplicate = _record_sale_inner(db, order)
    except DBAPIError as exc:
        if _is_missing_table(exc):
            return False  # inventory schema absent: leave commerce untouched
        raise
    except IntegrityError as exc:
        # CHECK(qty_on_hand ≥ 0) or concurrent-sale race → honest 422.
        raise _unprocessable("INVENTORY_INSUFFICIENT", INSUFFICIENT_MESSAGE) from exc
    if commit:
        db.commit()
    return duplicate


def _reverse_sale_inner(db: Session, order: Order) -> bool:
    """Inner restoration work (runs inside a SAVEPOINT; no commit/rollback)."""
    sales = repository.list_sale_movements(db, DEFAULT_STORE_ID, order.id)
    if not sales:
        return False
    if repository.first_return_movement(db, DEFAULT_STORE_ID, order.id) is not None:
        return True
    for sale in sales:
        item = repository.get_or_create_item(db, DEFAULT_STORE_ID, sale.variant_id)
        before = item.qty_on_hand
        after = before + sale.qty
        item.qty_on_hand = after
        db.add(
            StockMovement(
                store_id=DEFAULT_STORE_ID,
                inventory_item_id=item.id,
                variant_id=sale.variant_id,
                movement_type="return_in",
                qty=sale.qty,
                qty_before=before,
                qty_after=after,
                reference_type="order_sale",
                reference_id=order.id,
                reason="Order cancelled.",
                created_by=order.farmer_user_id,
            )
        )
    db.flush()
    return False


def reverse_order_sale(db: Session, order: Order, *, commit: bool = False) -> bool:
    """Restore stock for a cancelled order (same transaction, idempotent).

    No-op when no sale movement exists (e.g. pending → cancelled). Returns
    True when the restoration already happened.
    """
    try:
        with db.begin_nested():
            duplicate = _reverse_sale_inner(db, order)
    except DBAPIError as exc:
        if _is_missing_table(exc):
            return False  # inventory schema absent: leave commerce untouched
        raise
    except IntegrityError:
        # Lost a concurrent-restoration race: the winner's rows stand.
        return True
    if commit:
        db.commit()
    return duplicate
