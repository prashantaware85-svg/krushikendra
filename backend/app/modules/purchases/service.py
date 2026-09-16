"""Purchase draft policy + receive/cancel transitions.

Money convention: integer paise everywhere; quantities are ``Decimal``.
Server math always wins: ``line_total = round(qty × unit_cost)``,
``subtotal = Σ lines``, ``total = subtotal − discount + other_charges``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import User
from app.models.inventory import (
    DEFAULT_STORE_ID,
    InventoryItem,
    Purchase,
    PurchaseItem,
    StockMovement,
)
from app.modules.purchases import repository
from app.modules.purchases.schemas import (
    PurchaseActionOut,
    PurchaseCreate,
    PurchaseItemCreate,
    PurchaseItemOut,
    PurchaseOut,
    PurchasePage,
    PurchaseUpdate,
)

PURCHASE_STATUSES = ("draft", "received", "cancelled")


def _unprocessable(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def _not_found(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


def _line_total_paise(qty: Decimal, unit_cost_paise: int) -> int:
    try:
        return int((qty * Decimal(unit_cost_paise)).to_integral_value(rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise _unprocessable("PURCHASE_LINE_INVALID", "Invalid qty/unit_cost.") from exc


def _recompute(
    purchase: Purchase, items: list[PurchaseItem], *, enforce_non_negative: bool = True
) -> None:
    """Recompute server-side totals; never trust client totals."""
    purchase.subtotal_paise = sum(i.line_total_paise for i in items)
    total = purchase.subtotal_paise - purchase.discount_paise + purchase.other_charges_paise
    if enforce_non_negative and total < 0:
        raise _unprocessable("PURCHASE_TOTAL_NEGATIVE", "Purchase total cannot be negative.")
    purchase.total_paise = total


def _to_out(db: Session, purchase: Purchase) -> PurchaseOut:
    out = PurchaseOut.model_validate(purchase)
    out.items = [
        PurchaseItemOut.model_validate(i) for i in repository.list_items(db, purchase.id)
    ]
    return out


def _draft_only(purchase: Purchase) -> None:
    if purchase.status != "draft":
        raise _unprocessable(
            "PURCHASE_NOT_DRAFT",
            f"Only draft purchases can be changed (is {purchase.status}).",
        )


def _get(db: Session, purchase_id: uuid.UUID) -> Purchase:
    purchase = repository.get_purchase(db, DEFAULT_STORE_ID, purchase_id)
    if purchase is None:
        raise _not_found("PURCHASE_NOT_FOUND", "Purchase not found.")
    return purchase


# ── CRUD (draft flow) ───────────────────────────────────────────────
def list_purchases(
    db: Session, *, status_filter: str | None = None, limit: int = 20, offset: int = 0
) -> PurchasePage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if status_filter is not None and status_filter not in PURCHASE_STATUSES:
        raise _unprocessable(
            "PURCHASE_STATUS_INVALID",
            f"status must be one of {PURCHASE_STATUSES}.",
        )
    rows = repository.list_purchases(
        db, DEFAULT_STORE_ID, status=status_filter, limit=limit, offset=offset
    )
    return PurchasePage(
        purchases=[_to_out(db, p) for p in rows],
        total=repository.count_purchases(db, DEFAULT_STORE_ID, status=status_filter),
        limit=limit,
        offset=offset,
    )


def create_purchase(db: Session, user: User, payload: PurchaseCreate) -> PurchaseOut:
    if payload.supplier_id is not None and repository.get_supplier(
        db, DEFAULT_STORE_ID, payload.supplier_id
    ) is None:
        raise _not_found("SUPPLIER_NOT_FOUND", "Supplier not found.")
    purchase = None
    for _ in range(3):  # human-readable number; retry once on random collision
        candidate = Purchase(
            store_id=DEFAULT_STORE_ID,
            supplier_id=payload.supplier_id,
            purchase_number=f"PO-{uuid.uuid4().hex[:8].upper()}",
            purchase_date=payload.purchase_date,
            subtotal_paise=0,
            discount_paise=payload.discount_paise,
            other_charges_paise=payload.other_charges_paise,
            total_paise=0,
            status="draft",
            created_by=user.id,
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        purchase = candidate
        break
    if purchase is None:
        raise _unprocessable("PURCHASE_NUMBER_CONFLICT", "Could not allocate a purchase number.")
    try:
        # Empty draft is header scaffolding (discount may precede lines): the
        # non-negative invariant is enforced on every content mutation and at
        # receive, never from client totals.
        _recompute(purchase, [], enforce_non_negative=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(purchase)
    return _to_out(db, purchase)


def get_purchase(db: Session, purchase_id: uuid.UUID) -> PurchaseOut:
    return _to_out(db, _get(db, purchase_id))


def update_purchase(
    db: Session, purchase_id: uuid.UUID, payload: PurchaseUpdate
) -> PurchaseOut:
    purchase = _get(db, purchase_id)
    _draft_only(purchase)
    data = payload.model_dump(exclude_unset=True)
    data.pop("notes", None)  # accepted but not persisted (no column in Step 16 model)
    if "supplier_id" in data and data["supplier_id"] is not None:
        if repository.get_supplier(db, DEFAULT_STORE_ID, data["supplier_id"]) is None:
            raise _not_found("SUPPLIER_NOT_FOUND", "Supplier not found.")
    for field in ("supplier_id", "purchase_date", "discount_paise", "other_charges_paise"):
        if field in data:
            setattr(purchase, field, data[field])
    try:
        _recompute(purchase, repository.list_items(db, purchase.id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(purchase)
    return _to_out(db, purchase)


def list_items(db: Session, purchase_id: uuid.UUID) -> list[PurchaseItemOut]:
    purchase = _get(db, purchase_id)
    return [PurchaseItemOut.model_validate(i) for i in repository.list_items(db, purchase.id)]


def add_item(
    db: Session, purchase_id: uuid.UUID, payload: PurchaseItemCreate
) -> PurchaseItemOut:
    purchase = _get(db, purchase_id)
    _draft_only(purchase)
    item = PurchaseItem(
        purchase_id=purchase.id,
        variant_id=payload.variant_id,
        qty=payload.qty,
        unit_cost_paise=payload.unit_cost_paise,
        line_total_paise=_line_total_paise(payload.qty, payload.unit_cost_paise),
    )
    db.add(item)
    try:
        db.flush()  # flush first: the listing below already includes the new row
        _recompute(purchase, repository.list_items(db, purchase.id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(item)
    return PurchaseItemOut.model_validate(item)


def remove_item(db: Session, purchase_id: uuid.UUID, item_id: uuid.UUID) -> PurchaseOut:
    purchase = _get(db, purchase_id)
    _draft_only(purchase)
    item = repository.get_item(db, purchase.id, item_id)
    if item is None:
        raise _not_found("PURCHASE_ITEM_NOT_FOUND", "Purchase item not found.")
    db.delete(item)
    try:
        db.flush()  # flush first so the listing below excludes the deleted row
        _recompute(purchase, repository.list_items(db, purchase.id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(purchase)
    return _to_out(db, purchase)


# ── Receive / cancel ────────────────────────────────────────────────
def receive_purchase(db: Session, purchase_id: uuid.UUID) -> PurchaseActionOut:
    """draft → received (single transaction). Idempotent: already-received
    returns the current purchase with ``duplicate=True``; cancelled → 422."""
    purchase = _get(db, purchase_id)
    if purchase.status == "cancelled":
        raise _unprocessable("PURCHASE_CANCELLED", "Cancelled purchases cannot be received.")
    if purchase.status == "received":
        out = _to_out(db, purchase)
        return PurchaseActionOut(**out.model_dump(), duplicate=True)
    _draft_only(purchase)
    try:
        items = repository.list_items(db, purchase.id)
        _recompute(purchase, items)
        for item in items:
            inv = db.scalar(
                select(InventoryItem).where(
                    InventoryItem.store_id == DEFAULT_STORE_ID,
                    InventoryItem.variant_id == item.variant_id,
                )
            )
            if inv is None:  # auto-create only on purchase/opening/adjustment_in
                inv = InventoryItem(
                    store_id=DEFAULT_STORE_ID,
                    variant_id=item.variant_id,
                    qty_on_hand=Decimal("0"),
                    qty_reserved=Decimal("0"),
                    reorder_level=Decimal("0"),
                )
                db.add(inv)
                db.flush()
            before = inv.qty_on_hand
            after = before + item.qty
            inv.qty_on_hand = after
            db.add(
                StockMovement(
                    store_id=DEFAULT_STORE_ID,
                    inventory_item_id=inv.id,
                    variant_id=item.variant_id,
                    movement_type="purchase",
                    qty=item.qty,
                    qty_before=before,
                    qty_after=after,
                    reference_type="purchase_receipt",
                    reference_id=purchase.id,
                    reason=None,
                    created_by=purchase.created_by,
                )
            )
        purchase.status = "received"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _unprocessable(
            "PURCHASE_RECEIVE_CONFLICT",
            "Purchase could not be received (already received or conflicting lines).",
        ) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(purchase)
    out = _to_out(db, purchase)
    return PurchaseActionOut(**out.model_dump(), duplicate=False)


def cancel_purchase(db: Session, purchase_id: uuid.UUID) -> PurchaseActionOut:
    """draft → cancelled. received → 422; cancelled is idempotent."""
    purchase = _get(db, purchase_id)
    if purchase.status == "received":
        raise _unprocessable(
            "PURCHASE_ALREADY_RECEIVED", "Received purchases cannot be cancelled."
        )
    if purchase.status == "cancelled":
        out = _to_out(db, purchase)
        return PurchaseActionOut(**out.model_dump(), duplicate=True)
    _draft_only(purchase)
    purchase.status = "cancelled"
    db.commit()
    db.refresh(purchase)
    out = _to_out(db, purchase)
    return PurchaseActionOut(**out.model_dump(), duplicate=False)
