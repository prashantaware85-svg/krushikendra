"""Supplier schemas (Pydantic v2). GSTIN is stored-only: light format
treatment (strip whitespace, max 20 chars) — NO GST validation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mobile_number: str | None = Field(default=None, max_length=15)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    gstin: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank.")
        return value

    @field_validator("gstin")
    @classmethod
    def _light_gstin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = "".join(str(value).split())
        if len(compact) > 20:
            raise ValueError("gstin must be at most 20 characters.")
        return compact or None


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    mobile_number: str | None = Field(default=None, max_length=15)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    gstin: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank.")
        return value

    @field_validator("gstin")
    @classmethod
    def _light_gstin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = "".join(str(value).split())
        if len(compact) > 20:
            raise ValueError("gstin must be at most 20 characters.")
        return compact or None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    mobile_number: str | None = None
    email: str | None = None
    address: str | None = None
    gstin: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierPage(BaseModel):
    suppliers: list[SupplierOut]
    total: int
    limit: int
    offset: int
