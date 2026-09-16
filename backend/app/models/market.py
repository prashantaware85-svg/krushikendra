"""Market ORM models (factual mandi price data only — no selling).

Contracts: ``docs/market-prices.md``, ``backend/README.md`` (market
endpoints), ``apps/web/lib/api.ts`` (commodity / market / price shapes).

Commodity ≠ crop by design: market sources use their own naming, so no
FK links to ``farm_crops`` here (a future mapping table can join them).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Market(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A mandi / market yard (admin-curated catalogue)."""

    __tablename__ = "markets"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    state: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    taluka: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    village: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketCommodity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A tradable commodity (admin-curated catalogue)."""

    __tablename__ = "market_commodities"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    variety: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    local_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="quintal")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketPrice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One price quote: what the price was (``price_date``) vs when it was
    ingested (``fetched_at``). Money stored as Float per contract; formatted
    to 2 dp strings at the API boundary."""

    __tablename__ = "market_prices"

    commodity_id: Mapped[object] = mapped_column(
        Uuid, ForeignKey("market_commodities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    market_id: Mapped[object] = mapped_column(
        Uuid, ForeignKey("markets.id", ondelete="CASCADE"), index=True, nullable=False
    )

    price_per_quintal: Mapped[float] = mapped_column(Float, nullable=False)
    modal_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    min_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    max_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)

    price_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="quintal")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
