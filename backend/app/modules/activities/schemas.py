"""Activity Pydantic v2 contracts (mirrors ``Activity`` / ``ActivityWrite`` / ``Timeline``)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ActivityType = Literal[
    "land_preparation",
    "sowing",
    "transplanting",
    "irrigation",
    "fertilizer_application",
    "pesticide_application",
    "fungicide_application",
    "herbicide_application",
    "weeding",
    "interculture",
    "pruning",
    "scouting",
    "harvesting",
    "other",
]

ActivityStatus = Literal["planned", "completed", "skipped", "cancelled"]


class ActivityCreate(BaseModel):
    activity_type: ActivityType = "other"
    title: str = Field(max_length=256)
    description: str | None = None
    activity_date: date | str
    status: ActivityStatus = "planned"
    quantity: float | str | None = None
    quantity_unit: str | None = Field(default=None, max_length=32)
    cost: float | str | None = None
    cost_amount: float | str | None = None
    notes: str | None = None


class ActivityUpdate(BaseModel):
    activity_type: ActivityType | None = None
    title: str | None = Field(default=None, max_length=256)
    description: str | None = None
    activity_date: date | str | None = None
    status: ActivityStatus | None = None
    quantity: float | str | None = None
    quantity_unit: str | None = Field(default=None, max_length=32)
    cost: float | str | None = None
    cost_amount: float | str | None = None
    notes: str | None = None


class ActivityRead(BaseModel):
    id: str
    farm_crop_id: str
    activity_type: str
    title: str
    description: str | None = None
    activity_date: str
    status: str
    quantity: str | None = None
    quantity_unit: str | None = None
    cost: str | None = None
    notes: str | None = None
    created_at: str | None = None


class TimelineRead(BaseModel):
    farm_id: str
    crop_id: str
    crop_name: str
    activities: list[ActivityRead] = Field(default_factory=list)
