"""0012: create Krushi Store catalogue (categories, products, variants, images)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_create_store"
down_revision = "0011_create_pest_disease"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint("name", name=op.f("uq_product_categories_name")),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_price_paise", sa.Integer(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["product_categories.id"],
            name=op.f("fk_products_category_id_product_categories"),
            ondelete="SET NULL",
        ),
    )
    op.create_index(op.f("ix_products_name"), "products", ["name"])
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"])
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_paise", sa.Integer(), nullable=True),
        sa.Column("stock_qty", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_product_variants_product_id"), "product_variants", ["product_id"]
    )
    op.create_table(
        "product_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("image_path", sa.String(512), nullable=False),
        sa.Column("alt_text", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_images_product_id_products"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_product_images_product_id"), "product_images", ["product_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_images_product_id"), table_name="product_images")
    op.drop_table("product_images")
    op.drop_index(op.f("ix_product_variants_product_id"), table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_table("products")
    op.drop_table("product_categories")
