"""0018: create POS counter-billing tables (Step 18: bills + items + counter)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_create_pos"
down_revision = "0017_create_store_staff"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())

_SALE_STATUSES = ("draft", "completed", "cancelled")
_PAYMENT_STATUSES = ("pending", "paid", "partial", "credit")
_PAYMENT_MODES = ("cash", "upi", "card", "credit")
_SALE_LIST = ", ".join(f"'{s}'" for s in _SALE_STATUSES)
_PAYMENT_STATUS_LIST = ", ".join(f"'{s}'" for s in _PAYMENT_STATUSES)
_PAYMENT_MODE_LIST = ", ".join(f"'{m}'" for m in _PAYMENT_MODES)


def upgrade() -> None:
    op.create_table(
        "pos_bill_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    )
    op.create_table(
        "pos_bills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("bill_number", sa.String(40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("subtotal_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("other_charges_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payment_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("sale_status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("payment_mode", sa.String(20), nullable=True),
        sa.Column("amount_received_paise", sa.Integer(), nullable=True),
        sa.Column("amount_paid_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("balance_due_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payment_reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sold_by", sa.Uuid(), nullable=False),
        sa.Column("cancelled_by", sa.Uuid(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint(
            "store_id", "bill_number", name=op.f("uq_pos_bills_store_bill")
        ),
        sa.CheckConstraint(
            f"sale_status IN ({_SALE_LIST})",
            name=op.f("ck_pos_bills_sale_status"),
        ),
        sa.CheckConstraint(
            f"payment_status IN ({_PAYMENT_STATUS_LIST})",
            name=op.f("ck_pos_bills_payment_status"),
        ),
        sa.CheckConstraint(
            f"(payment_mode IS NULL OR payment_mode IN ({_PAYMENT_MODE_LIST}))",
            name=op.f("ck_pos_bills_payment_mode"),
        ),
    )
    op.create_index(op.f("ix_pos_bills_store_id"), "pos_bills", ["store_id"])
    op.create_index(op.f("ix_pos_bills_customer_id"), "pos_bills", ["customer_id"])
    op.create_index(
        "ix_pos_bills_store_created", "pos_bills", ["store_id", "created_at"]
    )
    op.create_table(
        "pos_bill_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pos_bill_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("product_name_snapshot", sa.String(200), nullable=False),
        sa.Column("variant_name_snapshot", sa.String(120), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.Column("discount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("line_total_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pos_bill_id"],
            ["pos_bills.id"],
            name=op.f("fk_pos_bill_items_pos_bill_id_pos_bills"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "qty > 0", name=op.f("ck_pos_bill_items_qty_positive")
        ),
    )
    op.create_index(
        op.f("ix_pos_bill_items_pos_bill_id"), "pos_bill_items", ["pos_bill_id"]
    )
    op.create_index(
        op.f("ix_pos_bill_items_variant_id"), "pos_bill_items", ["variant_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pos_bill_items_variant_id"), table_name="pos_bill_items")
    op.drop_index(op.f("ix_pos_bill_items_pos_bill_id"), table_name="pos_bill_items")
    op.drop_table("pos_bill_items")
    op.drop_index("ix_pos_bills_store_created", table_name="pos_bills")
    op.drop_index(op.f("ix_pos_bills_customer_id"), table_name="pos_bills")
    op.drop_index(op.f("ix_pos_bills_store_id"), table_name="pos_bills")
    op.drop_table("pos_bills")
    op.drop_table("pos_bill_counters")
