"""Market edge-case tests (SQLite, isolated engine, minimal app).

Covers: commodity search filter, detail 404s, nearby distance ordering,
history date-range validation, seeded source labels, and the no-GPS
farm-market-prices 404.
"""

from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register tables on Base.metadata
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.market import Market, MarketCommodity, MarketPrice
from app.modules.auth.dependencies import get_current_user
from app.modules.farms.router import router as farms_router
from app.modules.market.router import router as market_router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(bind=engine)

MISSING_ID = "00000000-0000-0000-0000-000000000000"


def make_client(user_id: str = "farmer-a") -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(farms_router)
    app.include_router(market_router)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    return TestClient(app, raise_server_exceptions=False)


def seed_market() -> dict:
    db = TestingSession()
    try:
        db.query(MarketPrice).delete()
        db.query(Market).delete()
        db.query(MarketCommodity).delete()
        db.commit()
        soy = MarketCommodity(name="Soybean", category="oilseed", unit="quintal")
        cotton = MarketCommodity(name="Cotton", category="fibre", unit="quintal")
        near = Market(
            name="Near Mandi", district="Nashik", state="Maharashtra",
            latitude=20.15, longitude=74.22,
        )
        far = Market(
            name="Far Mandi", district="Nashik", state="Maharashtra",
            latitude=21.00, longitude=75.00,
        )
        db.add_all([soy, cotton, near, far])
        db.commit()
        for obj in (soy, cotton, near, far):
            db.refresh(obj)
        db.add_all(
            [
                MarketPrice(
                    commodity_id=soy.id, market_id=near.id,
                    price_per_quintal=5100.0, modal_price=5100.0,
                    min_price=4950.0, max_price=5250.0,
                    price_date=date(2026, 9, 1),
                    source="SAMPLE (dev only)", unit="quintal", is_sample=True,
                ),
                MarketPrice(
                    commodity_id=cotton.id, market_id=near.id,
                    price_per_quintal=6200.0, modal_price=6200.0,
                    min_price=6000.0, max_price=6400.0,
                    price_date=date(2026, 9, 1),
                    source="SAMPLE (dev only)", unit="quintal", is_sample=True,
                ),
                MarketPrice(
                    commodity_id=soy.id, market_id=far.id,
                    price_per_quintal=5050.0, modal_price=5050.0,
                    min_price=4900.0, max_price=5200.0,
                    price_date=date(2026, 8, 25),
                    source="SAMPLE (dev only)", unit="quintal", is_sample=True,
                ),
            ]
        )
        db.commit()
        return {
            "soy": str(soy.id), "cotton": str(cotton.id),
            "near": str(near.id), "far": str(far.id),
        }
    finally:
        db.close()


def test_commodity_search_filter() -> None:
    client = make_client()
    ids = seed_market()
    response = client.get("/api/v1/market/commodities?search=soy")
    assert response.status_code == 200, response.text
    names = [c["name"] for c in response.json()]
    assert names == ["Soybean"]
    assert ids["cotton"] not in [c["id"] for c in response.json()]
    all_commodities = client.get("/api/v1/market/commodities")
    assert {c["name"] for c in all_commodities.json()} == {"Soybean", "Cotton"}


def test_market_detail_404() -> None:
    client = make_client()
    seed_market()
    for path in (
        f"/api/v1/market/markets/{MISSING_ID}",
        f"/api/v1/market/commodities/{MISSING_ID}",
    ):
        response = client.get(path)
        assert response.status_code == 404, (path, response.text)
    assert client.get(f"/api/v1/market/markets/{MISSING_ID}").json()["error"][
        "code"
    ] == "MARKET_NOT_FOUND"
    assert client.get(f"/api/v1/market/commodities/{MISSING_ID}").json()["error"][
        "code"
    ] == "COMMODITY_NOT_FOUND"


def test_nearby_ordering_by_distance() -> None:
    client = make_client()
    seed_market()
    response = client.get("/api/v1/market/nearby?latitude=20.15&longitude=74.22&radius_km=200")
    assert response.status_code == 200, response.text
    markets = response.json()
    assert [m["name"] for m in markets] == ["Near Mandi", "Far Mandi"]
    distances = [m["distance_km"] for m in markets]
    assert distances[0] == 0.0
    assert distances[0] < distances[1]
    assert all(d is not None for d in distances)


def test_history_date_range_validation_422() -> None:
    client = make_client()
    ids = seed_market()
    # No filter at all → 422.
    response = client.get("/api/v1/market/prices/history")
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "HISTORY_FILTER_REQUIRED"
    # Inverted range → 422.
    response = client.get(
        f"/api/v1/market/prices/history?commodity_id={ids['soy']}"
        "&from_date=2026-09-10&to_date=2026-09-01"
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "HISTORY_INVALID_RANGE"
    # Oversized range → 422.
    response = client.get(
        f"/api/v1/market/prices/history?commodity_id={ids['soy']}"
        "&from_date=2024-01-01&to_date=2026-09-01"
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "HISTORY_RANGE_TOO_LARGE"


def test_history_success() -> None:
    client = make_client()
    ids = seed_market()
    response = client.get(
        f"/api/v1/market/prices/history?commodity_id={ids['soy']}"
        "&from_date=2026-08-01&to_date=2026-09-05"
    )
    assert response.status_code == 200, response.text
    assert response.json()["data_state"] == "cached"
    assert len(response.json()["prices"]) == 2


def test_price_seed_source_label() -> None:
    client = make_client()
    seed_market()
    response = client.get("/api/v1/market/prices")
    assert response.status_code == 200, response.text
    prices = response.json()["prices"]
    assert prices, "expected seeded prices"
    for price in prices:
        assert price["source"] == "SAMPLE (dev only)"
        assert price["is_sample"] is True
        assert price["modal_price"] is not None


def test_prices_filter_by_commodity() -> None:
    client = make_client()
    ids = seed_market()
    response = client.get(f"/api/v1/market/prices?commodity_id={ids['cotton']}")
    assert response.status_code == 200, response.text
    prices = response.json()["prices"]
    assert prices
    assert {p["commodity"]["name"] for p in prices} == {"Cotton"}


def test_farm_market_prices_no_gps_404() -> None:
    client = make_client()
    seed_market()
    farm = client.post(
        "/api/v1/farms", json={"farm_name": "No GPS Plot", "area": "2"}
    ).json()
    response = client.get(f"/api/v1/farms/{farm['id']}/market-prices")
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "FARM_LOCATION_MISSING"
