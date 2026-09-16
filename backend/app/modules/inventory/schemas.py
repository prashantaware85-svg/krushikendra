"""Inventory schemas (Pydantic v2, Decimal quantities, int-free money —
this module carries NO money fields at all: no valuation by design)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Manual-adjustment vocabulary. ``sale``/``purchase`` are system-owned
#: (order hook / purchase receipt) and are rejected here with 422.
ADJUST_IN_TYPES = ("adjustment_in", "return_in", "opening_stock")
ADJUST_OUT_TYPES = ("adjustment_out", "damaged_out", "expired_out")
ADJUST_TYPES = ADJUST_IN_TYPES + ADJUST_OUT_TYPES
REASON_REQUIRED_TYPES = ("adjustment_in", "adjustment_out", "damaged_out", "expired_out")

#: Computed availability status.
STOCK_STATUSES = ("in", "low", "out")


class InventoryOut(BaseModel):
    """Farmer-safe availability view (no cost/internal fields exist here)."""

    variant_id: UUID
    variant_name: str | None = None
    product_id: UUID | None = None
    product_name: str | None = None
    category_id: UUID | None = None
    available: Decimal
    status: str


class InventoryDetailOut(InventoryOut):
    """Staff view: safe fields plus internal levels (movements stay staff-only)."""

    qty_on_hand: Decimal
    qty_reserved: Decimal
    reorder_level: Decimal
    reorder_qty: Decimal | None = None
    is_active: bool


class InventoryPage(BaseModel):
    items: list[InventoryOut]
    total: int
    limit: int
    offset: int


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    movement_type: str
    qty: Decimal
    qty_before: Decimal
    qty_after: Decimal
    reference_type: str | None = None
    reference_id: UUID | None = None
    reason: str | None = None
    created_at: datetime


class MovementPage(BaseModel):
    movements: list[MovementOut]
    total: int
    limit: int
    offset: int


class InventorySummaryOut(BaseModel):
    total: int
    in_stock: int
    low_stock: int
    out_of_stock: int
    recent_movements: list[MovementOut] = []


class AdjustIn(BaseModel):
    movement_type: str
    qty: Decimal
    reason: str | None = None

    @field_validator("qty")
    @classmethod
    def _positive_qty(cls, value: Decimal) -> Decimal:
        if value is None or value <= 0:
            raise ValueError("qty must be positive.")
        return value

    @field_validator("movement_type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in ADJUST_TYPES and value not in ("sale", "purchase"):
            raise ValueError(f"movement_type must be one of {ADJUST_TYPES}.")
        return value


class MovementFilter(BaseModel):
    movement_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ReorderLevelIn(BaseModel):
    """Manager-only reorder tuning. ``reorder_quantity`` maps to the
    ``reorder_qty`` column (None clears the suggestion)."""

    reorder_level: Decimal = Field(ge=0)
    reorder_quantity: Decimal | None = Field(default=None, gt=0)
