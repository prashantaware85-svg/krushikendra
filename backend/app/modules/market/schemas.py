"""Market Pydantic v2 contracts (mirrors commodity / market / price shapes)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DataState = Literal["fresh", "cached", "stale"]


class CommodityRead(BaseModel):
    id: str
    name: str
    category: str
    local_name: str | None = None
    variety: str | None = None
    unit: str


class MarketRead(BaseModel):
    id: str
    name: str
    state: str | None = None
    district: str | None = None
    taluka: str | None = None
    village: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    distance_km: float | None = None


class MarketPriceRead(BaseModel):
    id: str
    market: MarketRead
    commodity: CommodityRead
    price_date: str
    min_price: str | None = None
    max_price: str | None = None
    modal_price: str | None = None
    unit: str
    currency: str
    source: str | None = None
    is_sample: bool = False
    fetched_at: str | None = None


class PricesResponse(BaseModel):
    data_state: DataState
    prices: list[MarketPriceRead] = Field(default_factory=list)
    limit: int
    offset: int


class HistoryResponse(BaseModel):
    data_state: DataState
    prices: list[MarketPriceRead] = Field(default_factory=list)


class FarmMarketEntry(BaseModel):
    market: MarketRead
    prices: list[MarketPriceRead] = Field(default_factory=list)


class FarmMarketResponse(BaseModel):
    farm_id: str
    data_state: DataState
    markets: list[FarmMarketEntry] = Field(default_factory=list)
