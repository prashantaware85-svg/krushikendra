"""Crop Pydantic v2 contracts (mirrors ``Crop`` / ``CropWrite`` / ``CropVariety``)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.farms.schemas import AreaUnit

CropStatus = Literal["planned", "sown", "growing", "harvested", "failed", "cancelled"]
CropSeason = Literal["kharif", "rabi", "zaid", "perennial", "other"]


class CropCreate(BaseModel):
    crop_name: str = Field(max_length=64)
    variety_name: str | None = Field(default=None, max_length=64)
    crop_variety_id: str | None = None
    variety_id: str | None = None
    area: str | float | int | None = None
    area_acres: float | None = None
    area_unit: AreaUnit = "acre"
    season: CropSeason = "kharif"
    sowing_date: date | str | None = None
    expected_harvest_date: date | str | None = None
    status: CropStatus = "sown"
    notes: str | None = None


class CropUpdate(BaseModel):
    crop_name: str | None = Field(default=None, max_length=64)
    variety_name: str | None = Field(default=None, max_length=64)
    crop_variety_id: str | None = None
    variety_id: str | None = None
    area: str | float | int | None = None
    area_acres: float | None = None
    area_unit: AreaUnit | None = None
    season: CropSeason | None = None
    sowing_date: date | str | None = None
    expected_harvest_date: date | str | None = None
    status: CropStatus | None = None
    notes: str | None = None


class CropRead(BaseModel):
    id: str
    farm_id: str
    crop_variety_id: str | None = None
    crop_name: str
    variety_name: str | None = None
    area: str
    area_unit: str
    area_in_acres: float
    season: str
    sowing_date: str | None = None
    expected_harvest_date: str | None = None
    status: str
    notes: str | None = None


class CropVarietyRead(BaseModel):
    id: str
    crop_name: str
    variety_name: str | None = None
    crop_category: str
    duration_days: int | None = None
    season: str | None = None
