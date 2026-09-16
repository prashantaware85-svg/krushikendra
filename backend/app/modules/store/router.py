"""Store catalogue endpoints (thin: auth → service → response)."""

from __future__ import annotations

import mimetypes
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.store import service
from app.modules.store.schemas import (
    CategoryOut,
    ProductDetailOut,
    ProductImageOut,
    ProductListOut,
    ProductOut,
    VariantOut,
)

router = APIRouter(prefix="/store", tags=["store"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in service.list_categories(db)]


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> CategoryOut:
    return CategoryOut.model_validate(service.get_category(db, category_id))


@router.get("/products", response_model=ProductListOut)
def list_products(
    search: str | None = Query(default=None, max_length=120),
    category_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> ProductListOut:
    products = service.list_products(
        db, search=search, category_id=category_id, limit=limit, offset=offset
    )
    return ProductListOut(
        products=[ProductOut.model_validate(p) for p in products],
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product(
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> ProductDetailOut:
    product = service.get_product(db, product_id)
    detail = ProductDetailOut.model_validate(product)
    detail.variants = [
        VariantOut.model_validate(v) for v in service.list_variants(db, product_id)
    ]
    detail.images = [
        ProductImageOut.model_validate(i) for i in service.list_images(db, product_id)
    ]
    return detail


@router.get("/products/{product_id}/variants", response_model=list[VariantOut])
def list_variants(
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> list[VariantOut]:
    return [VariantOut.model_validate(v) for v in service.list_variants(db, product_id)]


@router.get("/products/{product_id}/images", response_model=list[ProductImageOut])
def list_images(
    product_id: uuid.UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> list[ProductImageOut]:
    return [ProductImageOut.model_validate(i) for i in service.list_images(db, product_id)]


@router.get("/images/{image_id}")
def serve_image(
    image_id: uuid.UUID,
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve catalogue image bytes (authed; no public URLs by design)."""
    _image, path = service.get_image_file(db, image_id)
    media_type, _ = mimetypes.guess_type(path.name)
    return FileResponse(path, media_type=media_type or "application/octet-stream")
