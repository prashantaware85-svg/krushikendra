"""Krushi Store catalogue models (Step 13 rebuild).

Display-only catalogue: categories → products → variants (packs) + images.
No cart/order/payment state lives here — commerce references variants by FK
and snapshots prices at checkout, so catalogue rows can evolve freely.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Shared browsable category (e.g. Seeds, Fertilizers)."""

    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Catalogue product. ``base_price_paise`` NULL = price on request."""

    __tablename__ = "products"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_price_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductVariant(Base, UUIDPrimaryKeyMixin):
    """Orderable pack of a product. NULL ``price_paise`` = unorderable."""

    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ProductImage(Base, UUIDPrimaryKeyMixin):
    """Catalogue photo. Bytes live on disk; only the relative path is stored."""

    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
