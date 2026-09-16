"""Commerce endpoints (thin: auth → service → response)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.commerce import service
from app.modules.commerce.schemas import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    CartItemCreate,
    CartItemUpdate,
    CartLineOut,
    CartOut,
    CartValidateOut,
    CheckoutCreate,
    OrderItemOut,
    OrderOut,
)

router = APIRouter(prefix="/store", tags=["commerce"])


# ── Cart ──────────────────────────────────────────────────────────────
@router.get("/cart", response_model=CartOut)
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    return service.get_cart(db, current_user)


@router.post("/cart/items", response_model=CartLineOut, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartLineOut:
    return service.add_item(db, current_user, payload.variant_id, payload.qty)


@router.put("/cart/items/{item_id}", response_model=CartLineOut)
def update_cart_item(
    item_id: uuid.UUID,
    payload: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartLineOut:
    return service.update_item(db, current_user, item_id, payload.qty)


@router.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.remove_item(db, current_user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.clear_cart(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cart/validate", response_model=CartValidateOut)
def validate_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartValidateOut:
    return service.validate_cart(db, current_user)


# ── Addresses ─────────────────────────────────────────────────────────
@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AddressOut]:
    return [AddressOut.model_validate(a) for a in service.list_addresses(db, current_user)]


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(
    payload: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressOut:
    return AddressOut.model_validate(service.create_address(db, current_user, payload))


@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(
    address_id: uuid.UUID,
    payload: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressOut:
    return AddressOut.model_validate(
        service.update_address(db, current_user, address_id, payload)
    )


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_address(db, current_user, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/addresses/{address_id}/default", response_model=AddressOut)
def set_default_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressOut:
    return AddressOut.model_validate(
        service.set_default_address(db, current_user, address_id)
    )


# ── Checkout + orders ─────────────────────────────────────────────────
@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderOut:
    return service.checkout(db, current_user, payload.address_id)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    return service.list_orders(db, current_user)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderOut:
    return service.get_order(db, current_user, order_id)


@router.get("/orders/{order_id}/items", response_model=list[OrderItemOut])
def list_order_items(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrderItemOut]:
    return service.list_order_items(db, current_user, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderOut:
    return service.cancel_order(db, current_user, order_id)
