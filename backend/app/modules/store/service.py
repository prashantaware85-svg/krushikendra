"""Store catalogue policy (read-only for farmers).

Image bytes live under ``settings.store_storage_dir``; only relative paths
are stored in the DB. Path traversal is rejected by resolving the candidate
and requiring it to stay inside the storage root.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.store import (
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
)
from app.modules.store import repository


def _not_found(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


def list_categories(db: Session) -> list[ProductCategory]:
    return repository.list_categories(db)


def get_category(db: Session, category_id: uuid.UUID) -> ProductCategory:
    category = repository.get_category(db, category_id)
    if category is None:
        raise _not_found("STORE_CATEGORY_NOT_FOUND", "Category not found.")
    return category


def list_products(
    db: Session,
    *,
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Product]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return repository.list_products(
        db, search=search, category_id=category_id, limit=limit, offset=offset
    )


def get_product(db: Session, product_id: uuid.UUID) -> Product:
    product = repository.get_product(db, product_id)
    if product is None or not product.is_active:
        raise _not_found("STORE_PRODUCT_NOT_FOUND", "Product not found.")
    return product


def list_variants(db: Session, product_id: uuid.UUID) -> list[ProductVariant]:
    get_product(db, product_id)  # 404 on unknown/inactive product
    return repository.list_variants(db, product_id)


def list_images(db: Session, product_id: uuid.UUID) -> list[ProductImage]:
    get_product(db, product_id)
    return repository.list_images(db, product_id)


def resolve_image_path(image: ProductImage) -> Path:
    """Absolute image file inside the store storage root (or raise 404)."""
    root = Path(get_settings().store_storage_dir).resolve()
    candidate = (root / image.image_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise _not_found("STORE_IMAGE_NOT_FOUND", "Image file not found.")
    if not candidate.is_file():
        raise _not_found("STORE_IMAGE_NOT_FOUND", "Image file not found.")
    return candidate


def get_image_file(db: Session, image_id: uuid.UUID) -> tuple[ProductImage, Path]:
    image = repository.get_image(db, image_id)
    if image is None:
        raise _not_found("STORE_IMAGE_NOT_FOUND", "Image not found.")
    # Inactive products hide their binaries too (uniform 404, no oracle).
    product = repository.get_product(db, image.product_id)
    if product is None or not product.is_active:
        raise _not_found("STORE_IMAGE_NOT_FOUND", "Image not found.")
    return image, resolve_image_path(image)
