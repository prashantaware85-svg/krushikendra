"""Market provider abstraction (service depends ONLY on ``MarketPriceProvider``).

Default is ``DisabledProvider`` (fails closed): labelled DB rows or
503 MARKET_DATA_UNAVAILABLE — never invented prices. A live source
(e.g. Agmarknet/eNAM) lands as a new subclass + factory entry.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class ProviderError(Exception):
    """Provider failure. Carries no secrets and no raw payloads."""


@dataclass
class PriceQuote:
    commodity_name: str
    market_name: str
    price_date: date
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    modal_price: Decimal | None = None
    unit: str = "quintal"
    currency: str = "INR"
    source: str = "disabled"


class MarketPriceProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def get_current_prices(
        self,
        commodity: str | None = None,
        market: str | None = None,
        price_date: date | None = None,
    ) -> list[PriceQuote]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_price_history(
        self,
        commodity: str | None = None,
        market: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PriceQuote]:
        raise NotImplementedError


class DisabledProvider(MarketPriceProvider):
    """No live source configured — refresh attempts fail closed."""

    name = "disabled"

    def get_current_prices(
        self,
        commodity: str | None = None,
        market: str | None = None,
        price_date: date | None = None,
    ) -> list[PriceQuote]:
        raise ProviderError("Market provider is disabled.")

    def get_price_history(
        self,
        commodity: str | None = None,
        market: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PriceQuote]:
        raise ProviderError("Market provider is disabled.")


def get_provider(name: str | None = None) -> MarketPriceProvider:
    """Factory (``MARKET_PROVIDER`` only allows ``disabled`` for now)."""
    raw = (name or os.getenv("MARKET_PROVIDER") or _configured_name()).strip().lower()
    return DisabledProvider()


def _configured_name() -> str:
    try:
        from app.core.config import get_settings

        return get_settings().market_provider
    except Exception:
        return "disabled"
