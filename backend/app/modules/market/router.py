"""Market thin router: catalogue, quotes, history, nearby, farm facts."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db

try:
    from app.modules.auth.dependencies import get_current_user
except ImportError:  # pragma: no cover - fallback when auth is not restored

    def get_current_user():  # type: ignore[no-redef]
        raise AppError("Authentication is unavailable.", code="NOT_AUTHENTICATED", status_code=401)

from app.modules.market import schemas, service

router = APIRouter(prefix="/api/v1", tags=["market"])


@router.get("/market/commodities", response_model=list[schemas.CommodityRead])
def list_commodities(
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.CommodityRead]:
    return service.list_commodities(db, search)


@router.get("/market/commodities/{commodity_id}", response_model=schemas.CommodityRead)
def get_commodity(
    commodity_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.CommodityRead:
    return service.get_commodity_detail(db, commodity_id)


@router.get("/market/markets", response_model=list[schemas.MarketRead])
def list_markets(
    state: str | None = None,
    district: str | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.MarketRead]:
    return service.list_markets(db, state, district)


@router.get("/market/markets/{market_id}", response_model=schemas.MarketRead)
def get_market(
    market_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.MarketRead:
    return service.get_market_detail(db, market_id)


@router.get("/market/prices", response_model=schemas.PricesResponse)
def list_prices(
    commodity_id: str | None = None,
    market_id: str | None = None,
    state: str | None = None,
    district: str | None = None,
    price_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.PricesResponse:
    return service.list_prices(
        db,
        commodity_id=commodity_id,
        market_id=market_id,
        state=state,
        district=district,
        price_date=price_date,
        limit=limit,
        offset=offset,
    )


@router.get("/market/prices/history", response_model=schemas.HistoryResponse)
def price_history(
    commodity_id: str | None = None,
    market_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.HistoryResponse:
    return service.price_history(
        db,
        commodity_id=commodity_id,
        market_id=market_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/market/nearby", response_model=list[schemas.MarketRead])
def nearby_markets(
    latitude: float,
    longitude: float,
    radius_km: float = 50.0,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[schemas.MarketRead]:
    return service.nearby_markets(db, latitude, longitude, radius_km)


@router.get("/farms/{farm_id}/market-prices", response_model=schemas.FarmMarketResponse)
def farm_market_prices(
    farm_id: str,
    radius_km: float = 100.0,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.FarmMarketResponse:
    return service.farm_market_prices(db, current_user, farm_id, radius_km)
