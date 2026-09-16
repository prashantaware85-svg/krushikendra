"""Store catalogue reads (active products only for farmers)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.store import Product, ProductCategory, ProductImage, ProductVariant


def list_categories(db: Session) -> list[ProductCategory]:
    return list(
        db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    )


def get_category(db: Session, category_id: uuid.UUID) -> ProductCategory | None:
    return db.get(ProductCategory, category_id)


def list_products(
    db: Session,
    *,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Product]:
    stmt = select(Product).where(Product.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Product.name.ilike(like), Product.description.ilike(like))
        )
    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def count_products(
    db: Session,
    *,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
) -> int:
    stmt = select(func.count()).select_from(Product).where(
        Product.is_active.is_(True)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Product.name.ilike(like), Product.description.ilike(like))
        )
    return int(db.scalar(stmt) or 0)


def get_product(db: Session, product_id: uuid.UUID) -> Product | None:
    return db.get(Product, product_id)


def list_variants(db: Session, product_id: uuid.UUID) -> list[ProductVariant]:
    stmt = (
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(ProductVariant.name)
    )
    return list(db.scalars(stmt).all())


def list_images(db: Session, product_id: uuid.UUID) -> list[ProductImage]:
    stmt = select(ProductImage).where(ProductImage.product_id == product_id)
    return list(db.scalars(stmt).all())


def get_image(db: Session, image_id: uuid.UUID) -> ProductImage | None:
    return db.get(ProductImage, image_id)
