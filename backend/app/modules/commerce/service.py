"""Commerce policy: server-side totals, single-transaction checkout.

STRICT SEPARATION:
- This module NEVER touches payments or khata tables. Checkout always leaves
  ``payment_status="pending"``; Step 15 owns everything after that.
- Totals always recompute from live variant rows; client totals are ignored.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth import User
from app.models.commerce import (
    ORDER_MACHINE,
    Cart,
    CartItem,
    DeliveryAddress,
    Order,
    OrderItem,
    OrderStatusHistory,
)
from app.models.store import Product, ProductVariant
from app.modules.commerce import repository
from app.modules.commerce.schemas import (
    AddressCreate,
    AddressUpdate,
    CartIssue,
    CartLineOut,
    CartOut,
    CartValidateOut,
    OrderItemOut,
    OrderOut,
)


def _err(code: str, message: str, status_code: int) -> AppError:
    return AppError(message, code=code, status_code=status_code)


def _not_found(code: str, message: str) -> AppError:
    return _err(code, message, status.HTTP_404_NOT_FOUND)


def _unprocessable(code: str, message: str) -> AppError:
    return _err(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY)


def _delivery_charge_paise() -> int:
    try:
        return int(Decimal(get_settings().order_delivery_charge) * 100)
    except (InvalidOperation, ValueError, TypeError):
        return 0


# ── Validation ────────────────────────────────────────────────────────
def _check_line(
    item: CartItem, variant: ProductVariant | None, product: Product | None
) -> CartIssue | None:
    settings = get_settings()
    if variant is None:
        return CartIssue(
            code="VARIANT_NOT_FOUND",
            message="This item is no longer available.",
            item_id=item.id,
            variant_id=item.variant_id,
        )
    if not (1 <= item.qty <= settings.cart_max_qty_per_item):
        return CartIssue(
            code="QTY_LIMIT",
            message=f"Quantity must be between 1 and {settings.cart_max_qty_per_item}.",
            item_id=item.id,
            variant_id=item.variant_id,
        )
    if variant.price_paise is None:
        return CartIssue(
            code="PRICE_ON_REQUEST",
            message="Price is available on request — this item cannot be ordered online.",
            item_id=item.id,
            variant_id=item.variant_id,
        )
    if product is not None and not product.is_active:
        return CartIssue(
            code="PRODUCT_INACTIVE",
            message="This product is currently unavailable.",
            item_id=item.id,
            variant_id=item.variant_id,
        )
    if item.qty > variant.stock_qty:
        return CartIssue(
            code="INSUFFICIENT_STOCK",
            message=f"Only {variant.stock_qty} in stock.",
            item_id=item.id,
            variant_id=item.variant_id,
        )
    return None


def validate_cart(db: Session, user: User) -> CartValidateOut:
    """Report per-line issues; never silently removes lines."""
    cart = repository.get_cart(db, user.id)
    if cart is None:
        return CartValidateOut(valid=True, issues=[], subtotal_paise=0)
    items = repository.list_cart_items(db, cart.id)
    issues: list[CartIssue] = []
    subtotal = 0
    for item in items:
        variant = repository.get_variant(db, item.variant_id)
        product = (
            repository.get_product(db, variant.product_id) if variant else None
        )
        issue = _check_line(item, variant, product)
        if issue is not None:
            issues.append(issue)
        elif variant is not None and variant.price_paise is not None:
            subtotal += variant.price_paise * item.qty
    return CartValidateOut(valid=not issues, issues=issues, subtotal_paise=subtotal)


def _line_out(
    db: Session, item: CartItem, variant: ProductVariant | None
) -> CartLineOut:
    product = repository.get_product(db, variant.product_id) if variant else None
    price = variant.price_paise if variant else None
    return CartLineOut(
        item_id=item.id,
        variant_id=item.variant_id,
        variant_name=variant.name if variant else "Unavailable item",
        product_name=product.name if product else None,
        qty=item.qty,
        unit_price_paise=price,
        line_total_paise=price * item.qty if price is not None else None,
        price_on_request=price is None,
    )


def get_cart(db: Session, user: User) -> CartOut:
    cart = repository.get_or_create_cart(db, user.id)
    db.commit()
    lines = [
        _line_out(db, item, repository.get_variant(db, item.variant_id))
        for item in repository.list_cart_items(db, cart.id)
    ]
    subtotal = sum(line.line_total_paise or 0 for line in lines)
    return CartOut(items=lines, subtotal_paise=subtotal)


def add_item(db: Session, user: User, variant_id: uuid.UUID, qty: int) -> CartLineOut:
    settings = get_settings()
    if not 1 <= qty <= settings.cart_max_qty_per_item:
        raise _unprocessable(
            "QTY_LIMIT",
            f"Quantity must be between 1 and {settings.cart_max_qty_per_item}.",
        )
    variant = repository.get_variant(db, variant_id)
    if variant is None:
        raise _not_found("VARIANT_NOT_FOUND", "Product variant not found.")
    cart = repository.get_or_create_cart(db, user.id)
    existing = next(
        (
            i
            for i in repository.list_cart_items(db, cart.id)
            if i.variant_id == variant_id
        ),
        None,
    )
    if existing is not None:
        existing.qty = min(existing.qty + qty, settings.cart_max_qty_per_item)
        item = existing
    else:
        if repository.count_distinct_items(db, cart.id) >= settings.cart_max_items:
            raise _unprocessable(
                "CART_FULL",
                f"Cart holds at most {settings.cart_max_items} different items.",
            )
        item = CartItem(cart_id=cart.id, variant_id=variant_id, qty=qty)
        db.add(item)
    db.commit()
    db.refresh(item)
    return _line_out(db, item, variant)


def _owned_item(db: Session, user: User, item_id: uuid.UUID) -> CartItem:
    item = repository.get_cart_item(db, item_id)
    cart = repository.get_cart(db, user.id)
    if item is None or cart is None or item.cart_id != cart.id:
        raise _not_found("CART_ITEM_NOT_FOUND", "Cart item not found.")
    return item


def update_item(db: Session, user: User, item_id: uuid.UUID, qty: int) -> CartLineOut:
    settings = get_settings()
    if not 1 <= qty <= settings.cart_max_qty_per_item:
        raise _unprocessable(
            "QTY_LIMIT",
            f"Quantity must be between 1 and {settings.cart_max_qty_per_item}.",
        )
    item = _owned_item(db, user, item_id)
    item.qty = qty
    db.commit()
    db.refresh(item)
    return _line_out(db, item, repository.get_variant(db, item.variant_id))


def remove_item(db: Session, user: User, item_id: uuid.UUID) -> None:
    item = _owned_item(db, user, item_id)
    db.delete(item)
    db.commit()


def clear_cart(db: Session, user: User) -> None:
    cart = repository.get_or_create_cart(db, user.id)
    repository.delete_cart_items(db, cart.id)
    db.commit()


# ── Addresses ─────────────────────────────────────────────────────────
def list_addresses(db: Session, user: User) -> list[DeliveryAddress]:
    return repository.list_addresses(db, user.id)


def create_address(db: Session, user: User, payload: AddressCreate) -> DeliveryAddress:
    existing = repository.list_addresses(db, user.id)
    address = DeliveryAddress(
        farmer_user_id=user.id,
        label=payload.label.strip() if payload.label else None,
        line1=payload.line1.strip(),
        city=payload.city.strip(),
        state=payload.state.strip(),
        pincode=payload.pincode,
        phone=payload.phone,
        is_default=not existing,  # first created wins default
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def _owned_address(db: Session, user: User, address_id: uuid.UUID) -> DeliveryAddress:
    address = repository.get_address(db, user.id, address_id)
    if address is None:
        raise _not_found("ADDRESS_NOT_FOUND", "Delivery address not found.")
    return address


def update_address(
    db: Session, user: User, address_id: uuid.UUID, payload: AddressUpdate
) -> DeliveryAddress:
    address = _owned_address(db, user, address_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(address, field, value)
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, user: User, address_id: uuid.UUID) -> None:
    address = _owned_address(db, user, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        # Pass default to the newest remaining address.
        nxt = repository.newest_other_address(db, user.id, address_id)
        if nxt is not None:
            nxt.is_default = True
    db.commit()


def set_default_address(
    db: Session, user: User, address_id: uuid.UUID
) -> DeliveryAddress:
    address = _owned_address(db, user, address_id)
    for other in repository.list_addresses(db, user.id):
        other.is_default = other.id == address.id
    db.commit()
    db.refresh(address)
    return address


# ── Checkout (single transaction) ─────────────────────────────────────
def checkout(db: Session, user: User, address_id: uuid.UUID) -> OrderOut:
    cart = repository.get_or_create_cart(db, user.id)
    items = repository.list_cart_items(db, cart.id)
    if not items:
        raise _unprocessable("CART_EMPTY", "Cart is empty.")

    report = validate_cart(db, user)
    if not report.valid:
        codes = ", ".join(sorted({i.code for i in report.issues}))
        raise _unprocessable(
            "CART_INVALID", f"Cart cannot be checked out ({codes})."
        )

    address = repository.get_address(db, user.id, address_id)
    if address is None:
        raise _not_found("ADDRESS_NOT_FOUND", "Delivery address not found.")

    # Re-read live prices inside the transaction window.
    lines: list[tuple[CartItem, ProductVariant]] = []
    subtotal = 0
    for item in items:
        variant = repository.get_variant(db, item.variant_id)
        assert variant is not None and variant.price_paise is not None
        lines.append((item, variant))
        subtotal += variant.price_paise * item.qty
    delivery = _delivery_charge_paise()
    total = subtotal + delivery

    try:
        seq = repository.next_order_sequence(db)
        order = Order(
            order_number=f"KS-{seq:06d}",
            farmer_user_id=user.id,
            address_id=address.id,
            status="pending",
            subtotal_paise=subtotal,
            delivery_paise=delivery,
            total_paise=total,
            payment_status="pending",  # Step 15 owns everything after this.
            payment_ref=None,
        )
        db.add(order)
        db.flush()
        for item, variant in lines:
            db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    qty=item.qty,
                    unit_price_paise=variant.price_paise,
                )
            )
        db.add(OrderStatusHistory(order_id=order.id, from_status=None, to_status="pending"))
        repository.delete_cart_items(db, cart.id)
        db.commit()  # single commit — partial orders are impossible
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    return order_to_out(db, order)


# ── Orders ────────────────────────────────────────────────────────────
def order_to_out(db: Session, order: Order) -> OrderOut:
    items = repository.list_order_items(db, order.id)
    out = OrderOut.model_validate(order)
    out.items = [
        OrderItemOut(
            id=i.id,
            variant_id=i.variant_id,
            qty=i.qty,
            unit_price_paise=i.unit_price_paise,
            line_total_paise=i.unit_price_paise * i.qty,
        )
        for i in items
    ]
    return out


def list_orders(db: Session, user: User) -> list[OrderOut]:
    return [order_to_out(db, o) for o in repository.list_orders(db, user.id)]


def get_order(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    order = repository.get_order(db, user.id, order_id)
    if order is None:
        raise _not_found("ORDER_NOT_FOUND", "Order not found.")
    return order_to_out(db, order)


def list_order_items(db: Session, user: User, order_id: uuid.UUID) -> list[OrderItemOut]:
    return get_order(db, user, order_id).items


def transition_order(
    db: Session, order: Order, to_status: str, *, commit: bool = True
) -> Order:
    """Validate the status machine and append history (admin/future use)."""
    allowed = ORDER_MACHINE.get(order.status, ())
    if to_status not in allowed:
        raise _unprocessable(
            "ORDER_TRANSITION_INVALID",
            f"Cannot move order from {order.status} to {to_status}.",
        )
    from_status = order.status
    order.status = to_status
    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=from_status, to_status=to_status
        )
    )
    db.flush()
    if to_status == "confirmed":
        # Step 16 surgical hook: decrement tracked store inventory in the SAME
        # transaction (lazy import avoids a commerce↔inventory cycle). Raises
        # 422 on insufficient tracked stock; untracked variants are skipped so
        # pre-stock confirm flows behave exactly as before. Catalogue
        # ProductVariant.stock_qty stays legacy display (never touched).
        from app.modules.inventory import service as inventory_service

        inventory_service.record_order_sale(db, order, commit=False)
    elif to_status == "cancelled":
        # Restore previously recorded sale stock (no-op when no sale exists,
        # e.g. pending → cancelled; idempotent when already restored).
        from app.modules.inventory import service as inventory_service

        inventory_service.reverse_order_sale(db, order, commit=False)
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def cancel_order(db: Session, user: User, order_id: uuid.UUID) -> OrderOut:
    order = repository.get_order(db, user.id, order_id)
    if order is None:
        raise _not_found("ORDER_NOT_FOUND", "Order not found.")
    if order.status not in ("pending", "confirmed"):
        raise _unprocessable(
            "ORDER_CANCEL_INVALID",
            f"Only pending/confirmed orders can be cancelled (is {order.status}).",
        )
    transition_order(db, order, "cancelled")
    return order_to_out(db, order)


def admin_set_status(
    db: Session, farmer_id: uuid.UUID, order_id: uuid.UUID, to_status: str
) -> Order:
    """No route in this step — reserved for a future authorized admin layer."""
    order = db.get(Order, order_id)
    if order is None or order.farmer_user_id != farmer_id:
        raise _not_found("ORDER_NOT_FOUND", "Order not found.")
    return transition_order(db, order, to_status)
