"""Farms + soil Pydantic v2 contracts.

snake_case throughout, mirroring ``apps/web/lib/api.ts`` (``Farm``,
``FarmWrite``, ``Soil``, ``SoilWrite``). Measurements travel as JSON
strings (precision-safe); ``area_in_acres`` is a derived display helper.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

AreaUnit = Literal["acre", "hectare", "guntha"]


class FarmCreate(BaseModel):
    farm_name: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    area: str | float | int | None = None
    area_acres: float | None = None
    area_unit: AreaUnit = "acre"
    state: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    taluka: str | None = Field(default=None, max_length=64)
    village: str | None = Field(default=None, max_length=64)
    latitude: float | str | None = None
    longitude: float | str | None = None
    land_type: str | None = Field(default=None, max_length=32)
    soil_type: str | None = Field(default=None, max_length=32)
    irrigation_type: str | None = Field(default=None, max_length=32)
    water_source: str | None = Field(default=None, max_length=32)
    ownership_type: str | None = Field(default=None, max_length=32)


class FarmUpdate(BaseModel):
    farm_name: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=128)
    area: str | float | int | None = None
    area_acres: float | None = None
    area_unit: AreaUnit | None = None
    state: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    taluka: str | None = Field(default=None, max_length=64)
    village: str | None = Field(default=None, max_length=64)
    latitude: float | str | None = None
    longitude: float | str | None = None
    land_type: str | None = Field(default=None, max_length=32)
    soil_type: str | None = Field(default=None, max_length=32)
    irrigation_type: str | None = Field(default=None, max_length=32)
    water_source: str | None = Field(default=None, max_length=32)
    ownership_type: str | None = Field(default=None, max_length=32)


class FarmRead(BaseModel):
    id: str
    farm_name: str
    area: str
    area_unit: str
    area_in_acres: float
    state: str | None = None
    district: str | None = None
    taluka: str | None = None
    village: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    land_type: str | None = None
    soil_type: str | None = None
    irrigation_type: str | None = None
    water_source: str | None = None
    ownership_type: str | None = None


class SoilCreate(BaseModel):
    soil_type: str | None = Field(default=None, max_length=64)
    soil_test_available: bool = False
    soil_test_date: date | str | None = None
    tested_on: date | str | None = None
    ph: float | str | None = None
    organic_carbon: float | str | None = None
    nitrogen: float | str | None = None
    phosphorus: float | str | None = None
    potassium: float | str | None = None
    soil_test_document_reference: str | None = Field(default=None, max_length=256)


class SoilUpdate(BaseModel):
    soil_type: str | None = Field(default=None, max_length=64)
    soil_test_available: bool | None = None
    soil_test_date: date | str | None = None
    tested_on: date | str | None = None
    ph: float | str | None = None
    organic_carbon: float | str | None = None
    nitrogen: float | str | None = None
    phosphorus: float | str | None = None
    potassium: float | str | None = None
    soil_test_document_reference: str | None = Field(default=None, max_length=256)


class SoilRead(BaseModel):
    id: str
    farm_id: str
    soil_type: str | None = None
    soil_test_available: bool = False
    soil_test_date: str | None = None
    ph: str | None = None
    organic_carbon: str | None = None
    nitrogen: str | None = None
    phosphorus: str | None = None
    potassium: str | None = None
    soil_test_document_reference: str | None = None
