"""Health contracts (Pydantic v2; severity/status are display-only)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ObservationType = Literal["pest", "disease", "unknown", "other"]
Severity = Literal["low", "medium", "high", "unknown"]
ObsStatus = Literal["observed", "monitoring", "resolved", "recurring"]
ObsSource = Literal["farmer", "image_analysis", "expert", "other"]
ActionType = Literal[
    "monitoring",
    "sanitation",
    "pruning",
    "removal",
    "irrigation_adjustment",
    "fertilizer_adjustment",
    "biological_control",
    "chemical_application",
    "other",
]


class PestDiseaseOut(BaseModel):
    id: uuid.UUID
    name: str
    local_name: str | None
    scientific_name: str | None
    category: str | None
    description: str | None
    is_verified: bool


class LinkedAnalysisOut(BaseModel):
    id: uuid.UUID
    possible_condition: str | None
    confidence: str | None
    status: str


class HealthObservationWrite(BaseModel):
    observation_type: ObservationType = "unknown"
    pest_id: uuid.UUID | None = None
    disease_id: uuid.UUID | None = None
    observed_name: str | None = Field(default=None, max_length=256)
    observation_date: date | None = None
    severity: Severity = "unknown"
    affected_area: float | None = Field(default=None, ge=0)
    affected_area_unit: str | None = Field(default=None, max_length=16)
    symptoms: str | None = None
    notes: str | None = None
    status: ObsStatus = "observed"
    source: ObsSource = "farmer"
    linked_image_analysis_id: uuid.UUID | None = None


class HealthObservationOut(BaseModel):
    id: uuid.UUID
    farm_crop_id: uuid.UUID
    observation_type: str
    pest_id: uuid.UUID | None
    pest_name: str | None
    disease_id: uuid.UUID | None
    disease_name: str | None
    observed_name: str | None
    observation_date: date | None
    severity: str
    affected_area: str | None
    affected_area_unit: str | None
    symptoms: str | None
    notes: str | None
    status: str
    source: str
    has_photos: bool
    linked_analysis: LinkedAnalysisOut | None


class HealthActionWrite(BaseModel):
    action_date: date | None = None
    action_type: ActionType
    description: str = Field(min_length=1)
    product_name: str | None = Field(default=None, max_length=128)
    quantity: float | None = Field(default=None, ge=0)
    quantity_unit: str | None = Field(default=None, max_length=16)
    notes: str | None = None


class HealthActionOut(BaseModel):
    id: uuid.UUID
    observation_id: uuid.UUID
    action_date: date | None
    action_type: str
    description: str | None
    product_name: str | None
    quantity: str | None
    quantity_unit: str | None
    notes: str | None
