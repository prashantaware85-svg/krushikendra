"""Store-staff RBAC models (Step 17).

Database-backed RBAC replacing the interim ``STORE_STAFF_MOBILES`` allowlist
(Step 16). Single-store scope: every row carries ``store_id`` filled from
``DEFAULT_STORE_ID`` (imported from the inventory model to avoid drift);
multi-store support is future work (replace the constant with a FK to a
stores table).

Coupling convention: ``user_id`` / ``actor_user_id`` / ``target_user_id``
are plain ``Uuid`` columns validated service-side — no hard FKs to
``users.id``. This mirrors the inventory/vision pattern
(``Purchase.created_by``, ``CropImageAnalysis.farmer_user_id`` are plain
UUIDs) and avoids cross-domain coupling while keeping index support.

Role hierarchy (extensible): ``admin > store_manager > store_staff`` via
``RBAC_RANK``. Future roles: add the value to ``STAFF_ROLES`` + the CHECK
constraint (migration) + a rank entry here — guards compare ranks, so no
router changes are needed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.inventory import DEFAULT_STORE_ID

#: Canonical staff roles. ``admin`` can manage staff (create / role change /
#: activate / deactivate / delete); ``store_manager`` can do operational
#: writes plus cancel purchases and reorder-level edits; ``store_staff`` can
#: do operational reads + creates + adjustments.
ADMIN_ROLE = "admin"
STORE_MANAGER_ROLE = "store_manager"
STORE_STAFF_ROLE = "store_staff"

STAFF_ROLES: tuple[str, ...] = (ADMIN_ROLE, STORE_MANAGER_ROLE, STORE_STAFF_ROLE)

#: Rank map for hierarchy checks (higher number = more privilege).
#: Extensible: new roles get a rank here; guards use ``>=`` comparisons.
RBAC_RANK: dict[str, int] = {
    STORE_STAFF_ROLE: 1,
    STORE_MANAGER_ROLE: 2,
    ADMIN_ROLE: 3,
}

_ROLE_LIST = ", ".join(f"'{r}'" for r in STAFF_ROLES)

#: Audit actions written to ``store_audit_logs`` on every staff mutation.
STAFF_AUDIT_ACTIONS: tuple[str, ...] = (
    "staff_create",
    "role_change",
    "activate",
    "deactivate",
    "delete",
)


class StoreStaff(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One staff membership row per (store, user). Active rows only grant access."""

    __tablename__ = "store_staff"
    __table_args__ = (
        UniqueConstraint("store_id", "user_id", name="uq_store_staff_store_user"),
        CheckConstraint(f"role IN ({_ROLE_LIST})", name="ck_store_staff_role"),
        Index("ix_store_staff_store_active", "store_id", "is_active"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, index=True, nullable=False, default=lambda: DEFAULT_STORE_ID
    )
    # Plain UUID (no hard FK to users.id) — validated service-side.
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StoreAuditLog(Base, UUIDPrimaryKeyMixin):
    """Immutable audit line for every staff mutation (actor/target/old/new).

    No edit/delete API — corrections are new rows. Never stores secrets
    (roles + active flags + ids + timestamp only).
    """

    __tablename__ = "store_audit_logs"
    __table_args__ = (
        Index("ix_store_audit_logs_store_created", "store_id", "created_at"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    # Plain UUIDs (no hard FKs to users.id) — validated service-side.
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    old_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    old_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
