"""POS persistence (store-scoped reads; no policy here)."""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import FarmerProfile, User
from app.models.inventory import DEFAULT_STORE_ID
from app.models.pos import PosBill, PosBillCounter, PosBillItem
from app.models.store import Product, ProductVariant


def next_bill_sequence(db: Session) -> int:
    """Allocate the next human-readable bill number (concurrency-safe)."""
    counter = PosBillCounter()
    db.add(counter)
    db.flush()
    return int(counter.id)


def get_variant(db: Session, variant_id: uuid.UUID) -> ProductVariant | None:
    return db.get(ProductVariant, variant_id)


def get_product(db: Session, product_id: uuid.UUID) -> Product | None:
    return db.get(Product, product_id)


def search_variants(
    db: Session, *, search: str | None = None
) -> list[tuple[ProductVariant, Product | None]]:
    """All variants + their product, optionally filtered by ILIKE over
    product name + variant name. No SKU/barcode fields exist in the
    catalogue, so search covers names only."""
    stmt = select(ProductVariant, Product).join(
        Product, Product.id == ProductVariant.product_id, isouter=True
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (Product.name.ilike(like)) | (ProductVariant.name.ilike(like))
        )
    stmt = stmt.order_by(Product.name.asc(), ProductVariant.name.asc())
    return [(v, p) for v, p in db.execute(stmt).all()]


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_profile_name(db: Session, user_id: uuid.UUID) -> str | None:
    profile = db.scalar(
        select(FarmerProfile).where(FarmerProfile.user_id == user_id)
    )
    if profile is not None and (profile.full_name or "").strip():
        return profile.full_name.strip()  # type: ignore[return-value]
    return None


def get_bill(db: Session, bill_id: uuid.UUID) -> PosBill | None:
    """Store-scoped bill lookup (other-store rows surface as None → 404)."""
    bill = db.get(PosBill, bill_id)
    if bill is None or bill.store_id != DEFAULT_STORE_ID:
        return None
    return bill


def list_bill_items(db: Session, bill_id: uuid.UUID) -> list[PosBillItem]:
    stmt = select(PosBillItem).where(PosBillItem.pos_bill_id == bill_id)
    return list(db.scalars(stmt).all())


def list_bills(
    db: Session,
    *,
    bill_number: str | None = None,
    customer_id: uuid.UUID | None = None,
    payment_mode: str | None = None,
    payment_status: str | None = None,
    sale_status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[PosBill]:
    stmt = select(PosBill).where(PosBill.store_id == DEFAULT_STORE_ID)
    if bill_number:
        stmt = stmt.where(PosBill.bill_number == bill_number)
    if customer_id is not None:
        stmt = stmt.where(PosBill.customer_id == customer_id)
    if payment_mode:
        stmt = stmt.where(PosBill.payment_mode == payment_mode)
    if payment_status:
        stmt = stmt.where(PosBill.payment_status == payment_status)
    if sale_status:
        stmt = stmt.where(PosBill.sale_status == sale_status)
    if since is not None:
        stmt = stmt.where(PosBill.created_at >= since)
    if until is not None:
        stmt = stmt.where(PosBill.created_at < until)
    stmt = stmt.order_by(PosBill.created_at.desc(), PosBill.id.desc())
    return list(db.scalars(stmt).all())


def count_bills_for_day(
    db: Session, *, since: datetime, until: datetime
) -> list[PosBill]:
    """Completed bills created within [since, until) for the summary."""
    stmt = (
        select(PosBill)
        .where(PosBill.store_id == DEFAULT_STORE_ID)
        .where(PosBill.sale_status == "completed")
        .where(PosBill.created_at >= since)
        .where(PosBill.created_at < until)
    )
    return list(db.scalars(stmt).all())


def day_bounds(day) -> tuple[datetime, datetime]:
    since = datetime.combine(day, time.min)
    from datetime import timedelta

    return since, since + timedelta(days=1)
