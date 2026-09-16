"""0016: create inventory tables (Step 16: suppliers/purchases/stock)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_create_inventory"
down_revision = "0015_backfill_step3_11_domains"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())

_MOVEMENT_TYPES = (
    "purchase",
    "sale",
    "adjustment_in",
    "adjustment_out",
    "return_in",
    "damaged_out",
    "expired_out",
    "transfer_in",
    "transfer_out",
    "opening_stock",
)
_MOVEMENT_TYPE_LIST = ", ".join(f"'{t}'" for t in _MOVEMENT_TYPES)


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("mobile_number", sa.String(15), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("gstin", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_suppliers_store_id"), "suppliers", ["store_id"])

    op.create_table(
        "purchases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("purchase_number", sa.String(40), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("subtotal_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discount_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "other_charges_paise", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("total_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_purchases_supplier_id_suppliers"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "store_id",
            "purchase_number",
            name=op.f("uq_purchases_store_id_purchase_number"),
        ),
    )
    op.create_index(op.f("ix_purchases_store_id"), "purchases", ["store_id"])
    op.create_index(op.f("ix_purchases_supplier_id"), "purchases", ["supplier_id"])
    op.create_index(op.f("ix_purchases_created_by"), "purchases", ["created_by"])

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost_paise", sa.Integer(), nullable=False),
        sa.Column("line_total_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["purchases.id"],
            name=op.f("fk_purchase_items_purchase_id_purchases"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_purchase_items_purchase_id"), "purchase_items", ["purchase_id"]
    )
    op.create_index(
        op.f("ix_purchase_items_variant_id"), "purchase_items", ["variant_id"]
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "qty_on_hand", sa.Numeric(14, 3), server_default="0", nullable=False
        ),
        sa.Column(
            "qty_reserved", sa.Numeric(14, 3), server_default="0", nullable=False
        ),
        sa.Column(
            "reorder_level", sa.Numeric(14, 3), server_default="0", nullable=False
        ),
        sa.Column("reorder_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint(
            "store_id",
            "variant_id",
            name=op.f("uq_inventory_items_store_id_variant_id"),
        ),
        sa.CheckConstraint(
            "qty_on_hand >= 0",
            name=op.f("ck_inventory_items_qty_on_hand_nonneg"),
        ),
        sa.CheckConstraint(
            "qty_reserved >= 0",
            name=op.f("ck_inventory_items_qty_reserved_nonneg"),
        ),
    )
    op.create_index(
        op.f("ix_inventory_items_store_id"), "inventory_items", ["store_id"]
    )
    op.create_index(
        op.f("ix_inventory_items_variant_id"), "inventory_items", ["variant_id"]
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("qty_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("qty_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"],
            ["inventory_items.id"],
            name=op.f("fk_stock_movements_inventory_item_id_inventory_items"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "reference_type",
            "reference_id",
            "movement_type",
            "inventory_item_id",
            name="uq_stock_move_ref_type",
        ),
        sa.CheckConstraint(
            f"movement_type IN ({_MOVEMENT_TYPE_LIST})",
            name=op.f("ck_stock_movements_movement_type"),
        ),
        sa.CheckConstraint(
            "qty > 0", name=op.f("ck_stock_movements_qty_positive")
        ),
    )
    op.create_index(op.f("ix_stock_movements_store_id"), "stock_movements", ["store_id"])
    op.create_index(
        op.f("ix_stock_movements_inventory_item_id"),
        "stock_movements",
        ["inventory_item_id"],
    )
    op.create_index(
        op.f("ix_stock_movements_variant_id"), "stock_movements", ["variant_id"]
    )
    op.create_index(
        op.f("ix_stock_movements_reference_type"),
        "stock_movements",
        ["reference_type"],
    )
    op.create_index(
        op.f("ix_stock_movements_reference_id"), "stock_movements", ["reference_id"]
    )
    op.create_index(
        "ix_stock_movements_item_created",
        "stock_movements",
        ["inventory_item_id", "created_at"],
    )
    op.create_index(
        "ix_stock_movements_variant_created",
        "stock_movements",
        ["variant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_movements_variant_created", table_name="stock_movements"
    )
    op.drop_index("ix_stock_movements_item_created", table_name="stock_movements")
    op.drop_index(
        op.f("ix_stock_movements_reference_id"), table_name="stock_movements"
    )
    op.drop_index(
        op.f("ix_stock_movements_reference_type"), table_name="stock_movements"
    )
    op.drop_index(
        op.f("ix_stock_movements_variant_id"), table_name="stock_movements"
    )
    op.drop_index(
        op.f("ix_stock_movements_inventory_item_id"), table_name="stock_movements"
    )
    op.drop_index(op.f("ix_stock_movements_store_id"), table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index(
        op.f("ix_inventory_items_variant_id"), table_name="inventory_items"
    )
    op.drop_index(op.f("ix_inventory_items_store_id"), table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_index(
        op.f("ix_purchase_items_variant_id"), table_name="purchase_items"
    )
    op.drop_index(
        op.f("ix_purchase_items_purchase_id"), table_name="purchase_items"
    )
    op.drop_table("purchase_items")
    op.drop_index(op.f("ix_purchases_created_by"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_supplier_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_store_id"), table_name="purchases")
    op.drop_table("purchases")
    op.drop_index(op.f("ix_suppliers_store_id"), table_name="suppliers")
    op.drop_table("suppliers")
