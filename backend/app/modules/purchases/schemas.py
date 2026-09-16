"""Purchase schemas (Pydantic v2).

Request bodies carry lines + discounts ONLY — subtotal/total are always
recomputed server-side, so client totals are structurally ignored (there is
no client-total field at all).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PurchaseCreate(BaseModel):
    supplier_id: UUID | None = None
    purchase_date: date = Field(default_factory=date.today)
    discount_paise: int = Field(default=0, ge=0)
    other_charges_paise: int = Field(default=0, ge=0)


class PurchaseUpdate(BaseModel):
    """Draft-only edits. ``notes`` is accepted for forward-compat but NOT
    persisted (the Step 16 Purchase model has no notes column)."""

    supplier_id: UUID | None = None
    purchase_date: date | None = None
    discount_paise: int | None = Field(default=None, ge=0)
    other_charges_paise: int | None = Field(default=None, ge=0)
    notes: str | None = None


class PurchaseItemCreate(BaseModel):
    variant_id: UUID
    qty: Decimal
    unit_cost_paise: int = Field(ge=0)

    @field_validator("qty")
    @classmethod
    def _positive_qty(cls, value: Decimal) -> Decimal:
        if value is None or value <= 0:
            raise ValueError("qty must be positive.")
        return value


class PurchaseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    qty: Decimal
    unit_cost_paise: int
    line_total_paise: int


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_number: str
    supplier_id: UUID | None = None
    purchase_date: date
    subtotal_paise: int
    discount_paise: int
    other_charges_paise: int
    total_paise: int
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseItemOut] = []


class PurchaseActionOut(PurchaseOut):
    """Receive/cancel response: the purchase plus an idempotency flag."""

    duplicate: bool = False


class PurchasePage(BaseModel):
    purchases: list[PurchaseOut]
    total: int
    limit: int
    offset: int
