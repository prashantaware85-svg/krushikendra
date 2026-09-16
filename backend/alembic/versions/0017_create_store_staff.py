"""0017: create store-staff RBAC tables (Step 17: DB-backed roles + audit)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_create_store_staff"
down_revision = "0016_create_inventory"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())

_STAFF_ROLES = ("admin", "store_manager", "store_staff")
_ROLE_LIST = ", ".join(f"'{r}'" for r in _STAFF_ROLES)


def upgrade() -> None:
    op.create_table(
        "store_staff",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.CheckConstraint(
            f"role IN ({_ROLE_LIST})",
            name=op.f("ck_store_staff_role"),
        ),
        sa.UniqueConstraint(
            "store_id",
            "user_id",
            name=op.f("uq_store_staff_store_user"),
        ),
    )
    op.create_index(op.f("ix_store_staff_store_id"), "store_staff", ["store_id"])
    op.create_index(op.f("ix_store_staff_user_id"), "store_staff", ["user_id"])
    op.create_index(
        "ix_store_staff_store_active", "store_staff", ["store_id", "is_active"]
    )

    op.create_table(
        "store_audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("old_role", sa.String(20), nullable=True),
        sa.Column("new_role", sa.String(20), nullable=True),
        sa.Column("old_active", sa.Boolean(), nullable=True),
        sa.Column("new_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
    )
    op.create_index(
        op.f("ix_store_audit_logs_store_id"), "store_audit_logs", ["store_id"]
    )
    op.create_index(
        "ix_store_audit_logs_store_created",
        "store_audit_logs",
        ["store_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_store_audit_logs_store_created", table_name="store_audit_logs"
    )
    op.drop_index(
        op.f("ix_store_audit_logs_store_id"), table_name="store_audit_logs"
    )
    op.drop_table("store_audit_logs")
    op.drop_index("ix_store_staff_store_active", table_name="store_staff")
    op.drop_index(op.f("ix_store_staff_user_id"), table_name="store_staff")
    op.drop_index(op.f("ix_store_staff_store_id"), table_name="store_staff")
    op.drop_table("store_staff")
