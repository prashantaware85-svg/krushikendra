"""Soil-test contracts (Pydantic v2; units shown next to values in UI)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

OPT_NUM = Field(default=None)


class SoilTestWrite(BaseModel):
    test_date: date | None = None
    laboratory_name: str | None = Field(default=None, max_length=128)
    report_number: str | None = Field(default=None, max_length=64)
    soil_type: str | None = Field(default=None, max_length=32)
    ph: float | None = Field(default=None, ge=0, le=14)
    electrical_conductivity: float | None = Field(default=None, ge=0, le=20)
    organic_carbon: float | None = Field(default=None, ge=0, le=100)
    nitrogen: float | None = Field(default=None, ge=0, le=2000)
    phosphorus: float | None = Field(default=None, ge=0, le=2000)
    potassium: float | None = Field(default=None, ge=0, le=2000)
    sulphur: float | None = Field(default=None, ge=0, le=500)
    zinc: float | None = Field(default=None, ge=0, le=1000)
    iron: float | None = Field(default=None, ge=0, le=1000)
    manganese: float | None = Field(default=None, ge=0, le=1000)
    copper: float | None = Field(default=None, ge=0, le=1000)
    boron: float | None = Field(default=None, ge=0, le=1000)
    notes: str | None = None


class SoilTestOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    test_date: date | None
    laboratory_name: str | None
    report_number: str | None
    soil_type: str | None
    ph: str | None
    electrical_conductivity: str | None
    organic_carbon: str | None
    nitrogen: str | None
    phosphorus: str | None
    potassium: str | None
    sulphur: str | None
    zinc: str | None
    iron: str | None
    manganese: str | None
    copper: str | None
    boron: str | None
    notes: str | None
    has_report: bool
