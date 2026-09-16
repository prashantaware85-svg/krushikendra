"""0014: create payments + khata ledger tables (Step 15)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_create_payments_khata"
down_revision = "0013_create_orders"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(30), server_default="mock", nullable=False),
        sa.Column("provider_ref", sa.String(120), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("raw_callback_json", sa.JSON(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payments_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_payments_order_id")),
        sa.UniqueConstraint("provider_ref", name=op.f("uq_payments_provider_ref")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_payments_idempotency_key")
        ),
    )
    op.create_table(
        "khata_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("entry_type", sa.String(10), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("balance_after_paise", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farmer_user_id"],
            ["users.id"],
            name=op.f("fk_khata_entries_farmer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_khata_entries_order_id_orders"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "entry_type IN ('debit', 'credit', 'payment')",
            name=op.f("ck_khata_entries_entry_type"),
        ),
        sa.CheckConstraint(
            "amount_paise > 0", name=op.f("ck_khata_entries_amount_positive")
        ),
    )
    op.create_index(
        op.f("ix_khata_entries_farmer_user_id"),
        "khata_entries",
        ["farmer_user_id"],
    )
    op.create_index(
        op.f("ix_khata_entries_order_id"), "khata_entries", ["order_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_khata_entries_order_id"), table_name="khata_entries"
    )
    op.drop_index(
        op.f("ix_khata_entries_farmer_user_id"), table_name="khata_entries"
    )
    op.drop_table("khata_entries")
    op.drop_table("payments")
