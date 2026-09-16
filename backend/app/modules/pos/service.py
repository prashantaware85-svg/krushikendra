"""POS counter-billing policy (Step 18).

Money convention: integer paise everywhere; quantities are ``Decimal``.
Server math always wins: line totals recompute from live variant rows;
client totals are never trusted. Draft bills hold intent only (NO stock
deduction); completion decrements stock atomically; cancellation restores
stock with offsetting ``return_in`` rows (immutable ledger, never edit).

Single store: users carry NO cross-store ``store_id`` — customer validation
checks existence + active only. Catalogue has NO SKU/barcode fields —
product search covers product name + variant name (ILIKE) only.

Discount rule: plain ``store_staff`` cashiers may grant at most
``settings.pos_staff_max_discount_paise`` (₹200) per bill;
``store_manager``/``admin`` are unlimited but the discount may never
exceed the subtotal (422 POS_DISCOUNT_INVALID).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth import User
from app.models.inventory import DEFAULT_STORE_ID, InventoryItem, StockMovement
from app.models.pos import (
    POS_PAYMENT_MODES,
    POS_PAYMENT_STATUSES,
    POS_SALE_STATUSES,
    PosBill,
    PosBillItem,
)
from app.models.staff import RBAC_RANK, STORE_MANAGER_ROLE, StoreStaff
from app.modules.inventory import repository as inv_repository
from app.modules.inventory.service import INSUFFICIENT_MESSAGE
from app.modules.khata import service as khata_service
from app.modules.pos import repository
from app.modules.pos.schemas import (
    PosBillCompleteOut,
    PosBillOut,
    PosBillPage,
    PosProductOut,
    PosReceiptOut,
)

REFUND_NOTE = "परतावा प्रक्रिया स्वतंत्रपणे करावी लागेल."
RECEIPT_FOOTER = "धन्यवाद! पुन्हा भेट द्या."
STORE_NAME = "Krushi Seva Kendra"


def _forbidden(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=403)


def _not_found(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _unprocessable(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=422)


def _line_total_paise(qty: Decimal, unit_price_paise: int) -> int:
    try:
        return int(
            (qty * Decimal(unit_price_paise)).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise _unprocessable("POS_LINE_INVALID", "Invalid qty/unit price.") from exc


def _available_of(item: InventoryItem | None, fallback: Decimal) -> Decimal:
    if item is None:
        return fallback
    return item.qty_on_hand - item.qty_reserved


def _emoji_for(item: InventoryItem | None, available: Decimal) -> str:
    if available <= 0:
        return "🔴"
    if item is not None and available <= item.reorder_level:
        return "🟠"
    return "🟢"


def _product_out(
    db: Session, variant_id: uuid.UUID
) -> PosProductOut | None:
    variant = repository.get_variant(db, variant_id)
    if variant is None:
        return None
    product = repository.get_product(db, variant.product_id)
    item = inv_repository.get_item(db, DEFAULT_STORE_ID, variant.id)
    fallback = Decimal(variant.stock_qty)
    available = _available_of(item, fallback)
    return PosProductOut(
        variant_id=variant.id,
        product_id=product.id if product else None,
        product_name=product.name if product else None,
        variant_name=variant.name,
        unit_price_paise=variant.price_paise,
        price_on_request=variant.price_paise is None,
        available=str(available),
        stock_status=_emoji_for(item, available),
    )


def list_products(db: Session, *, search: str | None = None) -> list[PosProductOut]:
    """Sellable catalogue for the counter: active products, price-on-request
    rows included and flagged (never filtered out). No costs/margins/
    reorder/movements are exposed."""
    rows = repository.search_variants(db, search=search)
    out: list[PosProductOut] = []
    for variant, product in rows:
        if product is not None and not product.is_active:
            continue
        item = inv_repository.get_item(db, DEFAULT_STORE_ID, variant.id)
        fallback = Decimal(variant.stock_qty)
        available = _available_of(item, fallback)
        out.append(
            PosProductOut(
                variant_id=variant.id,
                product_id=product.id if product else None,
                product_name=product.name if product else None,
                variant_name=variant.name,
                unit_price_paise=variant.price_paise,
                price_on_request=variant.price_paise is None,
                available=str(available),
                stock_status=_emoji_for(item, available),
            )
        )
    return out


def get_product(db: Session, variant_id: uuid.UUID) -> PosProductOut:
    row = _product_out(db, variant_id)
    if row is None:
        raise _not_found("POS_VARIANT_NOT_FOUND", "Product variant not found.")
    variant = repository.get_variant(db, variant_id)
    product = repository.get_product(db, variant.product_id) if variant else None
    if product is not None and not product.is_active:
        raise _not_found("POS_VARIANT_NOT_FOUND", "Product variant not found.")
    return row


def _to_out(db: Session, bill: PosBill) -> PosBillOut:
    items = repository.list_bill_items(db, bill.id)
    out = PosBillOut.model_validate(bill)
    from app.modules.pos.schemas import PosBillItemOut

    out.items = [PosBillItemOut.model_validate(i) for i in items]
    return out


def _check_discount_role(staff: StoreStaff, discount_paise: int) -> None:
    if discount_paise <= 0:
        return
    cap = get_settings().pos_staff_max_discount_paise
    rank = RBAC_RANK.get(staff.role, 0)
    if rank < RBAC_RANK[STORE_MANAGER_ROLE] and discount_paise > cap:
        raise _forbidden(
            "POS_DISCOUNT_LIMIT",
            f"Staff discount limit is {cap} paise on this bill.",
        )


def create_bill(
    db: Session, user: User, staff: StoreStaff, payload
) -> PosBillOut:
    """Create a draft bill. No stock deduction happens here."""
    if not payload.items:
        raise _unprocessable("POS_ITEMS_REQUIRED", "At least one item is required.")
    if payload.discount_paise < 0 or payload.other_charges_paise < 0:
        raise _unprocessable("POS_BILL_INVALID", "discount/other_charges must be >= 0.")
    if payload.payment_mode is not None and payload.payment_mode not in POS_PAYMENT_MODES:
        raise _unprocessable(
            "POS_PAYMENT_MODE_INVALID",
            f"payment_mode must be one of {POS_PAYMENT_MODES}.",
        )
    customer_id = payload.customer_id
    if customer_id is not None:
        customer = repository.get_user(db, customer_id)
        if customer is None or not customer.is_active:
            raise _not_found("CUSTOMER_NOT_FOUND", "Customer not found.")
    _check_discount_role(staff, payload.discount_paise)

    # Merge duplicate variant lines (sum qty) so per-line stock movements
    # stay unique per (reference, inventory line).
    merged: dict[uuid.UUID, Decimal] = {}
    order: list[uuid.UUID] = []
    for line in payload.items:
        try:
            qty = Decimal(line.qty)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise _unprocessable("POS_QTY_INVALID", "qty must be positive.") from exc
        if qty <= 0:
            raise _unprocessable("POS_QTY_INVALID", "qty must be positive.")
        if line.variant_id not in merged:
            order.append(line.variant_id)
            merged[line.variant_id] = qty
        else:
            merged[line.variant_id] += qty

    lines: list[tuple] = []
    subtotal = 0
    for variant_id in order:
        qty = merged[variant_id]
        variant = repository.get_variant(db, variant_id)
        if variant is None:
            raise _not_found("VARIANT_NOT_FOUND", "Product variant not found.")
        product = repository.get_product(db, variant.product_id)
        if product is not None and not product.is_active:
            raise _unprocessable(
                "PRODUCT_UNORDERABLE", "This product is currently unavailable."
            )
        if variant.price_paise is None:
            raise _unprocessable(
                "PRICE_ON_REQUEST",
                "Price is available on request — this item cannot be billed.",
            )
        line_total = _line_total_paise(qty, variant.price_paise)
        subtotal += line_total
        pname = product.name if product else variant.name
        lines.append((variant, pname, qty, variant.price_paise, line_total))

    if payload.discount_paise > subtotal:
        raise _unprocessable(
            "POS_DISCOUNT_INVALID", "discount cannot exceed the subtotal."
        )
    total = subtotal - payload.discount_paise + payload.other_charges_paise
    if total < 0:
        raise _unprocessable("POS_TOTAL_NEGATIVE", "Bill total cannot be negative.")

    try:
        from datetime import datetime, timezone

        year = datetime.now(timezone.utc).year
        seq = repository.next_bill_sequence(db)
        bill = PosBill(
            store_id=DEFAULT_STORE_ID,
            bill_number=f"KSK-{year}-{seq:06d}",
            customer_id=customer_id,
            subtotal_paise=subtotal,
            discount_paise=payload.discount_paise,
            other_charges_paise=payload.other_charges_paise,
            total_paise=total,
            payment_status="pending",
            sale_status="draft",
            payment_mode=None,
            amount_received_paise=None,
            amount_paid_paise=0,
            balance_due_paise=total,
            payment_reference=None,
            notes=(payload.notes or "").strip() or None,
            sold_by=user.id,
        )
        db.add(bill)
        db.flush()
        for variant, pname, qty, unit_price, line_total in lines:
            db.add(
                PosBillItem(
                    pos_bill_id=bill.id,
                    variant_id=variant.id,
                    product_name_snapshot=pname,
                    variant_name_snapshot=variant.name,
                    qty=qty,
                    unit_price_paise=unit_price,
                    discount_paise=0,
                    line_total_paise=line_total,
                )
            )
        db.commit()
    except AppError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _unprocessable("POS_BILL_INVALID", "Could not create bill.") from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(bill)
    return _to_out(db, bill)


def list_bills(
    db: Session,
    *,
    bill_number: str | None = None,
    customer_id: uuid.UUID | None = None,
    payment_mode: str | None = None,
    payment_status: str | None = None,
    sale_status: str | None = None,
    date_from=None,
    date_to=None,
    limit: int = 20,
    offset: int = 0,
) -> PosBillPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    if payment_mode is not None and payment_mode not in POS_PAYMENT_MODES:
        raise _unprocessable(
            "POS_PAYMENT_MODE_INVALID",
            f"payment_mode must be one of {POS_PAYMENT_MODES}.",
        )
    if payment_status is not None and payment_status not in POS_PAYMENT_STATUSES:
        raise _unprocessable(
            "POS_PAYMENT_STATUS_INVALID",
            f"payment_status must be one of {POS_PAYMENT_STATUSES}.",
        )
    if sale_status is not None and sale_status not in POS_SALE_STATUSES:
        raise _unprocessable(
            "POS_SALE_STATUS_INVALID",
            f"sale_status must be one of {POS_SALE_STATUSES}.",
        )
    from datetime import datetime, time, timedelta

    since = datetime.combine(date_from, time.min) if date_from else None
    until = None
    if date_to:
        until = datetime.combine(date_to, time.min) + timedelta(days=1)
    rows = repository.list_bills(
        db,
        bill_number=bill_number,
        customer_id=customer_id,
        payment_mode=payment_mode,
        payment_status=payment_status,
        sale_status=sale_status,
        since=since,
        until=until,
    )
    total = len(rows)
    page = rows[offset : offset + limit]
    return PosBillPage(
        bills=[_to_out(db, b) for b in page],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_bill(db: Session, bill_id: uuid.UUID) -> PosBillOut:
    bill = repository.get_bill(db, bill_id)
    if bill is None:
        raise _not_found("POS_BILL_NOT_FOUND", "Bill not found.")
    return _to_out(db, bill)


def complete_bill(
    db: Session, user: User, bill_id: uuid.UUID, payload
) -> PosBillCompleteOut:
    """Complete a draft bill atomically: stock + payments + khata in one
    transaction. Idempotent: completed → {duplicate: True} no-op."""
    bill = repository.get_bill(db, bill_id)
    if bill is None:
        raise _not_found("POS_BILL_NOT_FOUND", "Bill not found.")
    if bill.sale_status == "completed":
        return PosBillCompleteOut(bill=_to_out(db, bill), duplicate=True)
    if bill.sale_status == "cancelled":
        raise _unprocessable(
            "POS_BILL_CANCELLED", "Cancelled bills cannot be completed."
        )
    mode = payload.payment_mode
    if mode not in POS_PAYMENT_MODES:
        raise _unprocessable(
            "POS_PAYMENT_MODE_INVALID",
            f"payment_mode must be one of {POS_PAYMENT_MODES}.",
        )
    total = bill.total_paise
    amount_paid_opt = payload.amount_paid_paise
    is_partial = (
        amount_paid_opt is not None and amount_paid_opt != total
    )
    if amount_paid_opt is not None:
        if amount_paid_opt <= 0 or amount_paid_opt >= total:
            if not (total == 0 and amount_paid_opt == 0):
                raise _unprocessable(
                    "POS_PARTIAL_INVALID",
                    "amount_paid_paise must be > 0 and < total for partial payment.",
                )
    if mode == "credit":
        if bill.customer_id is None:
            raise _unprocessable(
                "POS_CUSTOMER_REQUIRED",
                "Credit bills require a customer.",
            )
        paid, balance, pstatus = 0, total, "credit"
        received = None
    elif is_partial:
        assert amount_paid_opt is not None
        if bill.customer_id is None:
            raise _unprocessable(
                "POS_CUSTOMER_REQUIRED",
                "Partial payments require a customer.",
            )
        paid, balance, pstatus = amount_paid_opt, total - amount_paid_opt, "partial"
        received = payload.amount_received_paise
        if mode == "cash":
            if received is None:
                raise _unprocessable(
                    "POS_PAYMENT_INSUFFICIENT",
                    "amount_received_paise is required for cash.",
                )
            if received < paid:
                raise _unprocessable(
                    "POS_PAYMENT_INSUFFICIENT",
                    "Amount received is less than the amount due.",
                )
    else:
        paid, balance, pstatus = total, 0, "paid"
        received = payload.amount_received_paise
        if mode == "cash":
            if received is None:
                raise _unprocessable(
                    "POS_PAYMENT_INSUFFICIENT",
                    "amount_received_paise is required for cash.",
                )
            if received < total:
                raise _unprocessable(
                    "POS_PAYMENT_INSUFFICIENT",
                    "Amount received is less than the amount due.",
                )
    reference = (payload.payment_reference or "").strip() or None

    try:
        items = repository.list_bill_items(db, bill.id)
        for line in items:
            item = inv_repository.get_item(db, DEFAULT_STORE_ID, line.variant_id)
            if item is None:
                continue  # untracked variant: no stock governance (mirror order-sale)
            if (item.qty_on_hand - item.qty_reserved) < line.qty:
                raise _unprocessable("INVENTORY_INSUFFICIENT", INSUFFICIENT_MESSAGE)
            before = item.qty_on_hand
            after = before - line.qty
            item.qty_on_hand = after
            db.add(
                StockMovement(
                    store_id=DEFAULT_STORE_ID,
                    inventory_item_id=item.id,
                    variant_id=line.variant_id,
                    movement_type="sale",
                    qty=line.qty,
                    qty_before=before,
                    qty_after=after,
                    reference_type="pos_sale",
                    reference_id=bill.id,
                    reason=None,
                    created_by=user.id,
                )
            )
        db.flush()
        if balance > 0:
            # balance>0 implies customer present (guarded above).
            assert bill.customer_id is not None
            khata_service.record_debit(
                db,
                farmer_id=bill.customer_id,
                amount_paise=balance,
                order_id=None,
                note=f"POS {bill.bill_number}",
                commit=False,
            )
        bill.payment_mode = mode
        bill.amount_received_paise = received
        bill.amount_paid_paise = paid
        bill.balance_due_paise = balance
        bill.payment_reference = reference
        bill.payment_status = pstatus
        bill.sale_status = "completed"
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
    db.refresh(bill)
    return PosBillCompleteOut(bill=_to_out(db, bill), duplicate=False)


def cancel_bill(
    db: Session, user: User, bill_id: uuid.UUID, reason: str | None = None
) -> PosBillCompleteOut:
    """Manager-only cancel. Draft → cancelled (no stock effect); completed →
    cancelled + one ``return_in`` per sale + Khata CREDIT reversal for
    credit/partial balances. Idempotent; never hard-deletes."""
    from app.modules.pos.schemas import PosBillCompleteOut as _Out

    bill = repository.get_bill(db, bill_id)
    if bill is None:
        raise _not_found("POS_BILL_NOT_FOUND", "Bill not found.")
    if bill.sale_status == "cancelled":
        return _Out(bill=_to_out(db, bill), duplicate=True)
    clean_reason = (reason or "").strip() or None
    try:
        if bill.sale_status == "completed":
            sales = inv_repository.list_pos_sale_movements(
                db, DEFAULT_STORE_ID, bill.id
            )
            if sales and (
                inv_repository.first_pos_return_movement(
                    db, DEFAULT_STORE_ID, bill.id
                )
                is None
            ):
                for sale in sales:
                    item = inv_repository.get_or_create_item(
                        db, DEFAULT_STORE_ID, sale.variant_id
                    )
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
                            reference_type="pos_sale",
                            reference_id=bill.id,
                            reason="POS bill cancelled.",
                            created_by=user.id,
                        )
                    )
            db.flush()
            if bill.balance_due_paise > 0 and bill.customer_id is not None:
                khata_service.record_credit(
                    db,
                    farmer_id=bill.customer_id,
                    amount_paise=bill.balance_due_paise,
                    order_id=None,
                    note=f"POS {bill.bill_number} cancelled",
                    commit=False,
                )
        bill.sale_status = "cancelled"
        bill.cancelled_by = user.id
        bill.cancel_reason = clean_reason
        db.commit()
    except AppError:
        db.rollback()
        raise
    except IntegrityError:
        # Lost a concurrent-restoration race: the winner's rows stand;
        # still mark cancelled.
        db.rollback()
        bill = repository.get_bill(db, bill_id)
        if bill is None:  # pragma: no cover - defensive
            raise _not_found("POS_BILL_NOT_FOUND", "Bill not found.")
        if bill.sale_status != "cancelled":
            bill.sale_status = "cancelled"
            bill.cancelled_by = user.id
            bill.cancel_reason = clean_reason
            db.commit()
            db.refresh(bill)
        return _Out(bill=_to_out(db, bill), duplicate=True)
    except Exception:
        db.rollback()
        raise
    db.refresh(bill)
    return _Out(bill=_to_out(db, bill), duplicate=False)


def get_receipt(db: Session, bill_id: uuid.UUID) -> PosReceiptOut:
    """Staff-facing JSON receipt. No internal IDs/secrets: cashier/customer
    are display names only (no UUIDs, no mobiles)."""
    from app.modules.pos.schemas import PosReceiptItem

    bill = repository.get_bill(db, bill_id)
    if bill is None:
        raise _not_found("POS_BILL_NOT_FOUND", "Bill not found.")
    items = repository.list_bill_items(db, bill.id)
    cashier = repository.get_profile_name(db, bill.sold_by) or "Staff"
    customer = None
    if bill.customer_id is not None:
        customer = repository.get_profile_name(db, bill.customer_id) or "Customer"
    if bill.payment_mode == "cash":
        change = (bill.amount_received_paise or 0) - bill.amount_paid_paise
        payment = {
            "mode": bill.payment_mode,
            "paid_paise": bill.amount_paid_paise,
            "received_paise": bill.amount_received_paise,
            "change_paise": change,
            "balance_due_paise": bill.balance_due_paise,
        }
    else:
        payment = {
            "mode": bill.payment_mode,
            "paid_paise": bill.amount_paid_paise,
            "balance_due_paise": bill.balance_due_paise,
            "reference": bill.payment_reference,
        }
    if bill.sale_status == "cancelled" and bill.payment_mode in (
        "cash",
        "upi",
        "card",
    ):
        payment["refund_note"] = REFUND_NOTE
    return PosReceiptOut(
        store={"name": STORE_NAME},
        bill_number=bill.bill_number,
        created_at=bill.created_at,
        cashier=cashier,
        customer=customer,
        items=[
            PosReceiptItem(
                product_name=i.product_name_snapshot,
                variant_name=i.variant_name_snapshot,
                qty=i.qty,
                unit_price_paise=i.unit_price_paise,
                line_total_paise=i.line_total_paise,
            )
            for i in items
        ],
        subtotal_paise=bill.subtotal_paise,
        discount_paise=bill.discount_paise,
        other_charges_paise=bill.other_charges_paise,
        total_paise=bill.total_paise,
        sale_status=bill.sale_status,
        payment_status=bill.payment_status,
        payment=payment,
        footer=RECEIPT_FOOTER,
    )


def get_summary(db: Session, day: date | None = None) -> dict:
    """Operational day summary over completed bills only (no profit/GST)."""
    from datetime import datetime

    target: date = day or datetime.now().date()
    since, until = repository.day_bounds(target)
    rows = repository.count_bills_for_day(db, since=since, until=until)
    breakdown: dict[str, dict[str, int]] = {
        m: {"bills": 0, "total_paise": 0} for m in POS_PAYMENT_MODES
    }
    total = 0
    for bill in rows:
        total += bill.total_paise
        mode = bill.payment_mode or "cash"
        if mode not in breakdown:
            breakdown[mode] = {"bills": 0, "total_paise": 0}
        breakdown[mode]["bills"] += 1
        breakdown[mode]["total_paise"] += bill.total_paise
    return {
        "date": target,
        "bills": len(rows),
        "total_paise": total,
        "breakdown": breakdown,
    }
