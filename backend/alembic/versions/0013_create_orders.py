"""0013: create commerce tables (carts, addresses, orders, history, counter)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_create_orders"
down_revision = "0012_create_store"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farmer_user_id"],
            ["users.id"],
            name=op.f("fk_carts_farmer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "farmer_user_id", name=op.f("uq_carts_farmer_user_id")
        ),
    )
    op.create_index(op.f("ix_carts_farmer_user_id"), "carts", ["farmer_user_id"])
    op.create_table(
        "cart_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cart_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            name=op.f("fk_cart_items_cart_id_carts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_cart_items_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "cart_id", "variant_id", name=op.f("uq_cart_items_cart_variant")
        ),
    )
    op.create_index(op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"])
    op.create_index(
        op.f("ix_cart_items_variant_id"), "cart_items", ["variant_id"]
    )
    op.create_table(
        "delivery_addresses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(60), nullable=True),
        sa.Column("line1", sa.String(255), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("pincode", sa.String(10), nullable=False),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farmer_user_id"],
            ["users.id"],
            name=op.f("fk_delivery_addresses_farmer_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_delivery_addresses_farmer_user_id"),
        "delivery_addresses",
        ["farmer_user_id"],
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_number", sa.String(20), nullable=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("address_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("subtotal_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivery_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_paise", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "payment_status", sa.String(20), server_default="pending", nullable=False
        ),
        sa.Column("payment_ref", sa.String(120), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farmer_user_id"],
            ["users.id"],
            name=op.f("fk_orders_farmer_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["address_id"],
            ["delivery_addresses.id"],
            name=op.f("fk_orders_address_id_delivery_addresses"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("order_number", name=op.f("uq_orders_order_number")),
    )
    op.create_index(op.f("ix_orders_farmer_user_id"), "orders", ["farmer_user_id"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price_paise", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_order_items_variant_id_product_variants"),
            ondelete="SET NULL",
        ),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_history_order_id_orders"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_order_status_history_order_id"),
        "order_status_history",
        ["order_id"],
    )
    op.create_table(
        "order_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    )


def downgrade() -> None:
    op.drop_table("order_counters")
    op.drop_index(
        op.f("ix_order_status_history_order_id"), table_name="order_status_history"
    )
    op.drop_table("order_status_history")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_farmer_user_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(
        op.f("ix_delivery_addresses_farmer_user_id"),
        table_name="delivery_addresses",
    )
    op.drop_table("delivery_addresses")
    op.drop_index(op.f("ix_cart_items_variant_id"), table_name="cart_items")
    op.drop_index(op.f("ix_cart_items_cart_id"), table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index(op.f("ix_carts_farmer_user_id"), table_name="carts")
    op.drop_table("carts")
