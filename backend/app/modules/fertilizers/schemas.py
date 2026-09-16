"""Fertilizer contracts (Pydantic v2; quantities stored verbatim)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

FertilizerType = Literal[
    "organic", "nitrogen", "phosphorus", "potassium", "micronutrient", "npk", "other"
]
QuantityUnit = Literal["kg", "quintal", "litre", "gram", "other"]


class FertilizerWrite(BaseModel):
    application_date: date
    fertilizer_name: str = Field(min_length=1, max_length=128)
    fertilizer_type: FertilizerType | None = None
    quantity: float = Field(gt=0)
    quantity_unit: QuantityUnit = "kg"
    application_method: str | None = Field(default=None, max_length=64)
    purpose: str | None = Field(default=None, max_length=256)
    notes: str | None = None
    record_activity: bool = True  # accepted for API parity; no-op in this rebuild


class FertilizerOut(BaseModel):
    id: uuid.UUID
    farm_crop_id: uuid.UUID
    application_date: date
    fertilizer_name: str
    fertilizer_type: str | None
    quantity: str
    quantity_unit: str
    application_method: str | None
    purpose: str | None
    notes: str | None
