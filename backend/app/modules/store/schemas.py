"""Store catalogue schemas (reads only — no farmer writes exist)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from uuid import UUID


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID | None
    name: str
    description: str | None
    base_price_paise: int | None
    is_active: bool


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    name: str
    price_paise: int | None
    stock_qty: int


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    alt_text: str | None


class ProductDetailOut(ProductOut):
    variants: list[VariantOut] = []
    images: list[ProductImageOut] = []


class ProductListOut(BaseModel):
    products: list[ProductOut]
    limit: int
    offset: int
