"""POS counter-billing schemas (Pydantic v2).

Money = integer paise everywhere (codebase convention, NO float).
Quantities are Decimal (fractional kgs/litres/units allowed).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PosProductOut(BaseModel):
    variant_id: UUID
    product_id: UUID | None = None
    product_name: str | None = None
    variant_name: str | None = None
    unit_price_paise: int | None = None
    price_on_request: bool = False
    # Decimal rendered as string (exact quantities, no float).
    available: str = "0"
    # Computed availability emoji: in→🟢 low→🟠 out→🔴.
    stock_status: str = "🔴"


class PosBillItemIn(BaseModel):
    variant_id: UUID
    qty: Decimal


class PosBillCreate(BaseModel):
    items: list[PosBillItemIn] = Field(min_length=1)
    customer_id: UUID | None = None
    discount_paise: int = Field(default=0, ge=0)
    other_charges_paise: int = Field(default=0, ge=0)
    payment_mode: str | None = None
    notes: str | None = None


class PosBillItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    product_name_snapshot: str
    variant_name_snapshot: str
    qty: Decimal
    unit_price_paise: int
    discount_paise: int = 0
    line_total_paise: int


class PosBillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bill_number: str
    customer_id: UUID | None = None
    subtotal_paise: int
    discount_paise: int
    other_charges_paise: int
    total_paise: int
    payment_status: str
    sale_status: str
    payment_mode: str | None = None
    amount_received_paise: int | None = None
    amount_paid_paise: int
    balance_due_paise: int
    payment_reference: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[PosBillItemOut] = []


class PosBillPage(BaseModel):
    bills: list[PosBillOut]
    total: int
    limit: int
    offset: int


class PosBillCompleteIn(BaseModel):
    payment_mode: str
    amount_received_paise: int | None = Field(default=None, ge=0)
    payment_reference: str | None = None
    amount_paid_paise: int | None = Field(default=None, ge=0)


class PosBillCompleteOut(BaseModel):
    bill: PosBillOut
    duplicate: bool = False


class PosBillCancelIn(BaseModel):
    reason: str | None = None


class PosBillCancelOut(BaseModel):
    bill: PosBillOut
    duplicate: bool = False


class PosReceiptItem(BaseModel):
    product_name: str
    variant_name: str
    qty: Decimal
    unit_price_paise: int
    line_total_paise: int


class PosReceiptOut(BaseModel):
    store: dict
    bill_number: str
    created_at: datetime
    cashier: str
    customer: str | None = None
    items: list[PosReceiptItem]
    subtotal_paise: int
    discount_paise: int
    other_charges_paise: int
    total_paise: int
    sale_status: str
    payment_status: str
    payment: dict
    footer: str


class PosSummaryOut(BaseModel):
    date: date
    bills: int
    total_paise: int
    breakdown: dict
