"""Staff RBAC schemas (Pydantic v2).

Create resolves the target login user by ``mobile_number`` (normalised via
``auth.security.normalize_mobile``) OR ``user_id`` — never creates login
accounts. Out schema exposes ids + role + flags only (no passwords/tokens).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.staff import STAFF_ROLES


class StaffCreate(BaseModel):
    mobile_number: str | None = Field(default=None, max_length=20)
    user_id: UUID | None = None
    role: str = Field(max_length=20)

    model_config = ConfigDict(extra="ignore")

    @field_validator("role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        if value not in STAFF_ROLES:
            raise ValueError(f"role must be one of {STAFF_ROLES}.")
        return value


class StaffRoleUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("role")
    @classmethod
    def _valid_role(cls, value: str | None) -> str | None:
        if value is not None and value not in STAFF_ROLES:
            raise ValueError(f"role must be one of {STAFF_ROLES}.")
        return value


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    mobile: str | None = None
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class StaffPage(BaseModel):
    staff: list[StaffOut]
    total: int
    limit: int
    offset: int
