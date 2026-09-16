"""Market flow: cache-first DB facts; disabled provider fails closed (facts only)."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import coerce_utc
from app.modules.farms import service as farms_service
from app.modules.market import repository, schemas
from app.modules.market.providers import MarketPriceProvider, ProviderError, get_provider

logger = logging.getLogger("krushi-seva")


def _money(value: float | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _market_read(market, *, distance_km: float | None = None) -> schemas.MarketRead:
    return schemas.MarketRead(
        id=str(market.id),
        name=market.name,
        state=market.state,
        district=market.district,
        taluka=market.taluka,
        village=market.village,
        latitude=None if market.latitude is None else str(market.latitude),
        longitude=None if market.longitude is None else str(market.longitude),
        distance_km=round(distance_km, 2) if distance_km is not None else None,
    )


def _commodity_read(commodity) -> schemas.CommodityRead:
    return schemas.CommodityRead(
        id=str(commodity.id),
        name=commodity.name,
        category=commodity.category,
        local_name=commodity.local_name,
        variety=commodity.variety,
        unit=commodity.unit,
    )


def _price_read(db: Session, row) -> schemas.MarketPriceRead:
    market = repository.get_market(db, row.market_id)
    commodity = repository.get_commodity(db, row.commodity_id)
    fetched = coerce_utc(row.fetched_at) if row.fetched_at else None
    return schemas.MarketPriceRead(
        id=str(row.id),
        market=_market_read(market) if market else schemas.MarketRead(id=str(row.market_id), name="Unknown"),
        commodity=(
            _commodity_read(commodity)
            if commodity
            else schemas.CommodityRead(id=str(row.commodity_id), name="Unknown", category="other", unit=row.unit)
        ),
        price_date=row.price_date.isoformat(),
        min_price=_money(row.min_price),
        max_price=_money(row.max_price),
        modal_price=_money(row.modal_price if row.modal_price is not None else row.price_per_quintal),
        unit=row.unit,
        currency=row.currency,
        source=row.source,
        is_sample=bool(row.is_sample),
        fetched_at=fetched.isoformat() if fetched else None,
    )


def _refresh_attempt(provider: MarketPriceProvider) -> None:
    """Best-effort provider refresh; failures are swallowed (DB facts stand)."""
    try:
        provider.get_current_prices()
    except ProviderError:
        logger.debug("Market provider refresh skipped (%s)", provider.name)
    except Exception:
        logger.warning("Market provider refresh failed", exc_info=False)


def list_commodities(db: Session, search: str | None = None) -> list[schemas.CommodityRead]:
    return [_commodity_read(c) for c in repository.list_commodities(db, search)]


def _filter_uuid(value: str | None, *, field: str):
    """Coerce an optional query-filter id (invalid → 422, not 500)."""
    if not value:
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)


def get_commodity_detail(db: Session, commodity_id: str) -> schemas.CommodityRead:
    commodity = repository.get_commodity(
        db,
        farms_service.parse_uuid(
            commodity_id, code="COMMODITY_NOT_FOUND", message="Commodity not found."
        ),
    )
    if commodity is None:
        raise AppError("Commodity not found.", code="COMMODITY_NOT_FOUND", status_code=404)
    return _commodity_read(commodity)


def list_markets(
    db: Session, state: str | None = None, district: str | None = None
) -> list[schemas.MarketRead]:
    return [_market_read(m) for m in repository.list_markets(db, state, district)]


def get_market_detail(db: Session, market_id: str) -> schemas.MarketRead:
    market = repository.get_market(
        db,
        farms_service.parse_uuid(
            market_id, code="MARKET_NOT_FOUND", message="Market not found."
        ),
    )
    if market is None:
        raise AppError("Market not found.", code="MARKET_NOT_FOUND", status_code=404)
    return _market_read(market)


def list_prices(
    db: Session,
    *,
    commodity_id: str | None = None,
    market_id: str | None = None,
    state: str | None = None,
    district: str | None = None,
    price_date: date | str | None = None,
    limit: int = 50,
    offset: int = 0,
    provider: MarketPriceProvider | None = None,
) -> schemas.PricesResponse:
    parsed_date = _parse_date(price_date, field="price_date") if price_date else None
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    _refresh_attempt(provider or get_provider())
    rows = repository.query_prices(
        db,
        commodity_id=_filter_uuid(commodity_id, field="commodity_id"),
        market_id=_filter_uuid(market_id, field="market_id"),
        state=state,
        district=district,
        price_date=parsed_date,
        limit=limit,
        offset=offset,
    )
    if not rows:
        raise AppError("Market data is unavailable.", code="MARKET_DATA_UNAVAILABLE", status_code=503)
    return schemas.PricesResponse(
        data_state="cached",
        prices=[_price_read(db, r) for r in rows],
        limit=limit,
        offset=offset,
    )


def price_history(
    db: Session,
    *,
    commodity_id: str | None = None,
    market_id: str | None = None,
    from_date: date | str | None = None,
    to_date: date | str | None = None,
    provider: MarketPriceProvider | None = None,
) -> schemas.HistoryResponse:
    if not commodity_id and not market_id:
        raise AppError(
            "commodity_id or market_id is required.",
            code="HISTORY_FILTER_REQUIRED",
            status_code=422,
        )
    start = _parse_date(from_date, field="from_date") if from_date else date.today() - timedelta(days=30)
    end = _parse_date(to_date, field="to_date") if to_date else date.today()
    if start > end:
        raise AppError("Invalid history range.", code="HISTORY_INVALID_RANGE", status_code=422)
    if (end - start).days > 366:
        raise AppError("History range too large.", code="HISTORY_RANGE_TOO_LARGE", status_code=422)
    _refresh_attempt(provider or get_provider())
    rows = repository.query_history(
        db,
        commodity_id=_filter_uuid(commodity_id, field="commodity_id"),
        market_id=_filter_uuid(market_id, field="market_id"),
        start=start,
        end=end,
    )
    if not rows:
        raise AppError("Market data is unavailable.", code="MARKET_DATA_UNAVAILABLE", status_code=503)
    return schemas.HistoryResponse(
        data_state="cached", prices=[_price_read(db, r) for r in rows]
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (PostGIS can replace this later, same signature)."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _nearby_pairs(
    db: Session, latitude: Any, longitude: Any, radius_km: float = 50.0
) -> list[tuple]:
    """ORM (market, distance) pairs, nearest-first (keeps UUID ids ORM-native)."""
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise AppError("Invalid location.", code="INVALID_LOCATION", status_code=422)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise AppError("Invalid location.", code="INVALID_LOCATION", status_code=422)
    radius = max(1.0, min(float(radius_km or 50.0), 500.0))
    pairs: list[tuple] = []
    for market in repository.geo_markets(db):
        distance = haversine_km(lat, lon, float(market.latitude), float(market.longitude))
        if distance <= radius:
            pairs.append((market, distance))
    pairs.sort(key=lambda pair: pair[1])
    return pairs


def nearby_markets(
    db: Session, latitude: Any, longitude: Any, radius_km: float = 50.0
) -> list[schemas.MarketRead]:
    return [
        _market_read(market, distance_km=distance)
        for market, distance in _nearby_pairs(db, latitude, longitude, radius_km)
    ]


def farm_market_prices(
    db: Session, user: Any, farm_id: str, radius_km: float = 100.0,
    provider: MarketPriceProvider | None = None,
) -> schemas.FarmMarketResponse:
    farm = farms_service.resolve_farm(db, user, farm_id)
    if farm.latitude is None or farm.longitude is None:
        raise AppError(
            "This farm has no GPS location yet. Add latitude and longitude to see nearby prices.",
            code="FARM_LOCATION_MISSING",
            status_code=404,
        )
    _refresh_attempt(provider or get_provider())
    pairs = _nearby_pairs(db, farm.latitude, farm.longitude, radius_km)
    prices = repository.latest_prices_for_markets(db, [m.id for m, _ in pairs])
    by_market: dict[str, list] = {}
    for row in prices:
        by_market.setdefault(str(row.market_id), []).append(row)
    entries = [
        schemas.FarmMarketEntry(
            market=_market_read(m, distance_km=d),
            prices=[_price_read(db, r) for r in by_market.get(str(m.id), [])],
        )
        for m, d in pairs
        if by_market.get(str(m.id))
    ]
    if not entries:
        raise AppError("Market data is unavailable.", code="MARKET_DATA_UNAVAILABLE", status_code=503)
    return schemas.FarmMarketResponse(farm_id=str(farm.id), data_state="cached", markets=entries)


def _parse_date(value: date | str | None, *, field: str) -> date:
    if isinstance(value, date):
        return value
    if value not in (None, ""):
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            pass
    raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)
