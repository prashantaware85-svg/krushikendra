"""Crop-image contracts (Pydantic v2 — no refs/paths/secrets)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisSourceOut(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source_name: str
    source_url: str | None = None
    score: float


class CropAnalysisOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_crop_id: uuid.UUID | None
    status: str
    provider: str
    model: str
    possible_condition: str | None
    confidence: str | None
    observations: list[str] = Field(default_factory=list)
    needs_info: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    image_quality: str | None = None
    quality_notes: str | None = None
    disclaimer: str
    sources: list[AnalysisSourceOut] = Field(default_factory=list)
    response_language: str
    is_mock: bool


class AnalysisHistoryItemOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_crop_id: uuid.UUID | None
    crop_name: str | None = None
    status: str
    possible_condition: str | None
    confidence: str | None
    created_at: str


class UploadForm(BaseModel):
    farm_id: uuid.UUID
    crop_id: uuid.UUID | None = None
    language: Literal["mr", "hi", "en"] = "mr"
