"""Farmer profile contracts (Pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

Language = Literal["en", "hi", "mr"]


class FarmerProfileRead(BaseModel):
    full_name: str | None = None
    preferred_language: Language = "en"
    state: str | None = None
    district: str | None = None
    taluka: str | None = None
    village: str | None = None


class FarmerProfileUpdate(BaseModel):
    full_name: str | None = None
    preferred_language: Language | None = None
    state: str | None = None
    district: str | None = None
    taluka: str | None = None
    village: str | None = None

    @field_validator("full_name")
    @classmethod
    def _name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Full name must not be empty.")
        return value
