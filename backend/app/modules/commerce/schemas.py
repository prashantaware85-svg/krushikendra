"""Commerce schemas.

Request bodies carry ids + quantities + addresses ONLY — prices/totals are
always recomputed server-side, so tampered totals are structurally ignored.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10 or digits[0] == "0":
        raise ValueError("Phone must be a 10-digit Indian mobile number.")
    return digits


def normalize_pincode(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 6:
        raise ValueError("Pincode must be 6 digits.")
    return digits


class CartItemCreate(BaseModel):
    variant_id: UUID
    qty: int


class CartItemUpdate(BaseModel):
    qty: int


class CartLineOut(BaseModel):
    item_id: UUID
    variant_id: UUID
    variant_name: str
    product_name: str | None
    qty: int
    unit_price_paise: int | None
    line_total_paise: int | None
    price_on_request: bool


class CartOut(BaseModel):
    items: list[CartLineOut]
    subtotal_paise: int
    currency: str = "INR"


class CartIssue(BaseModel):
    code: str
    message: str
    item_id: UUID | None = None
    variant_id: UUID | None = None


class CartValidateOut(BaseModel):
    valid: bool
    issues: list[CartIssue]
    subtotal_paise: int


class AddressCreate(BaseModel):
    label: str | None = None
    line1: str
    city: str
    state: str
    pincode: str
    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("pincode")
    @classmethod
    def _normalize_pincode(cls, value: str) -> str:
        return normalize_pincode(value)


class AddressUpdate(BaseModel):
    label: str | None = None
    line1: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return None if value is None else normalize_phone(value)

    @field_validator("pincode")
    @classmethod
    def _normalize_pincode(cls, value: str | None) -> str | None:
        return None if value is None else normalize_pincode(value)


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str | None
    line1: str
    city: str
    state: str
    pincode: str
    phone: str
    is_default: bool


class CheckoutCreate(BaseModel):
    """Extra fields (prices/totals) are ignored — server math always wins."""

    address_id: UUID


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID | None
    qty: int
    unit_price_paise: int
    line_total_paise: int = 0


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str | None
    status: str
    payment_status: str
    subtotal_paise: int
    delivery_paise: int
    total_paise: int
    payment_ref: str | None
    address_id: UUID | None
    created_at: datetime
    items: list[OrderItemOut] = []
