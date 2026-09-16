"""Market data access. Catalogue reads serve active rows only."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import Market, MarketCommodity, MarketPrice


def list_commodities(db: Session, search: str | None = None) -> list[MarketCommodity]:
    stmt = select(MarketCommodity).where(MarketCommodity.is_active.is_(True))
    if search:
        stmt = stmt.where(MarketCommodity.name.ilike(f"%{search}%"))
    return list(db.scalars(stmt.order_by(MarketCommodity.name)).all())


def get_commodity(db: Session, commodity_id: uuid.UUID | str) -> MarketCommodity | None:
    return db.scalars(
        select(MarketCommodity).where(
            MarketCommodity.id == commodity_id, MarketCommodity.is_active.is_(True)
        )
    ).first()


def list_markets(
    db: Session, state: str | None = None, district: str | None = None
) -> list[Market]:
    stmt = select(Market).where(Market.is_active.is_(True))
    if state:
        stmt = stmt.where(Market.state == state)
    if district:
        stmt = stmt.where(Market.district == district)
    return list(db.scalars(stmt.order_by(Market.name)).all())


def get_market(db: Session, market_id: uuid.UUID | str) -> Market | None:
    return db.scalars(
        select(Market).where(Market.id == market_id, Market.is_active.is_(True))
    ).first()


def query_prices(
    db: Session,
    *,
    commodity_id: uuid.UUID | str | None = None,
    market_id: uuid.UUID | str | None = None,
    state: str | None = None,
    district: str | None = None,
    price_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MarketPrice]:
    stmt = (
        select(MarketPrice)
        .join(Market, Market.id == MarketPrice.market_id)
        .join(MarketCommodity, MarketCommodity.id == MarketPrice.commodity_id)
        .where(Market.is_active.is_(True), MarketCommodity.is_active.is_(True))
    )
    if commodity_id:
        stmt = stmt.where(MarketPrice.commodity_id == commodity_id)
    if market_id:
        stmt = stmt.where(MarketPrice.market_id == market_id)
    if state:
        stmt = stmt.where(Market.state == state)
    if district:
        stmt = stmt.where(Market.district == district)
    if price_date:
        stmt = stmt.where(MarketPrice.price_date == price_date)
    stmt = stmt.order_by(MarketPrice.price_date.desc(), MarketPrice.fetched_at.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)).all())


def query_history(
    db: Session,
    *,
    commodity_id: uuid.UUID | str | None = None,
    market_id: uuid.UUID | str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[MarketPrice]:
    stmt = (
        select(MarketPrice)
        .join(Market, Market.id == MarketPrice.market_id)
        .join(MarketCommodity, MarketCommodity.id == MarketPrice.commodity_id)
        .where(Market.is_active.is_(True), MarketCommodity.is_active.is_(True))
    )
    if commodity_id:
        stmt = stmt.where(MarketPrice.commodity_id == commodity_id)
    if market_id:
        stmt = stmt.where(MarketPrice.market_id == market_id)
    if start:
        stmt = stmt.where(MarketPrice.price_date >= start)
    if end:
        stmt = stmt.where(MarketPrice.price_date <= end)
    return list(db.scalars(stmt.order_by(MarketPrice.price_date)).all())


def geo_markets(db: Session) -> list[Market]:
    """Active markets that carry GPS coordinates (nearby candidates)."""
    return list(
        db.scalars(
            select(Market).where(
                Market.is_active.is_(True),
                Market.latitude.is_not(None),
                Market.longitude.is_not(None),
            )
        ).all()
    )


def latest_prices_for_markets(
    db: Session, market_ids: list, *, limit_per_market: int = 10
) -> list[MarketPrice]:
    if not market_ids:
        return []
    rows = list(
        db.scalars(
            select(MarketPrice)
            .where(MarketPrice.market_id.in_(market_ids))
            .order_by(MarketPrice.price_date.desc(), MarketPrice.fetched_at.desc())
        ).all()
    )
    grouped: dict[str, list[MarketPrice]] = {}
    for row in rows:
        key = str(row.market_id)
        if len(grouped.setdefault(key, [])) < limit_per_market:
            grouped[key].append(row)
    ordered: list[MarketPrice] = []
    for group in grouped.values():
        ordered.extend(group)
    return ordered
