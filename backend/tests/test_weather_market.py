"""Weather + market tests: GPS gating, mock provider, disabled-first market (SQLite)."""

from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register tables on Base.metadata
import app.modules.weather.service as weather_service
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.market import Market, MarketCommodity, MarketPrice
from app.modules.auth.dependencies import get_current_user
from app.modules.farms.router import router as farms_router
from app.modules.market.router import router as market_router
from app.modules.weather.providers import MockProvider
from app.modules.weather.router import router as weather_router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def make_client(user_id: str = "farmer-a") -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(farms_router, prefix="/api/v1")  # mirror main.py mounting
    app.include_router(weather_router, prefix="/api/v1")  # mirror main.py mounting
    app.include_router(market_router, prefix="/api/v1")  # mirror main.py mounting

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)
    return TestClient(app, raise_server_exceptions=False)


def _farm(client: TestClient, **overrides) -> dict:
    payload = {"farm_name": "Weather Plot", "area": "3", "area_unit": "acre"}
    payload.update(overrides)
    response = client.post("/api/v1/farms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_farm_weather_without_gps_returns_404() -> None:
    client = make_client()
    farm = _farm(client)
    response = client.get(f"/api/v1/farms/{farm['id']}/weather/current")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FARM_LOCATION_MISSING"


def test_weather_current_with_mock_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        weather_service, "get_provider", lambda name=None: MockProvider()
    )
    client = make_client()
    response = client.get("/api/v1/weather/current?latitude=20.55&longitude=74.5")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_state"] == "fresh"
    assert body["provider"] == "mock"

    farm = _farm(client, farm_name="GPS Plot", latitude=20.55, longitude=74.5)
    farm_weather = client.get(f"/api/v1/farms/{farm['id']}/weather/forecast")
    assert farm_weather.status_code == 200, farm_weather.text
    assert len(farm_weather.json()["days"]) == 7


def test_market_empty_503_then_seeded_200() -> None:
    client = make_client()
    empty = client.get("/api/v1/market/prices")
    assert empty.status_code == 503
    assert empty.json()["error"]["code"] == "MARKET_DATA_UNAVAILABLE"

    db = TestingSession()
    try:
        commodity = MarketCommodity(name="Soybean", category="oilseed", unit="quintal")
        market = Market(
            name="Lasalgaon", district="Nashik", state="Maharashtra",
            latitude=20.15, longitude=74.22,
        )
        db.add_all([commodity, market])
        db.commit()
        db.refresh(commodity)
        db.refresh(market)
        db.add(
            MarketPrice(
                commodity_id=commodity.id,
                market_id=market.id,
                price_per_quintal=5100.0,
                modal_price=5100.0,
                min_price=4950.0,
                max_price=5250.0,
                price_date=date(2026, 9, 1),
                source="SAMPLE (dev only)",
                unit="quintal",
                is_sample=True,
            )
        )
        db.commit()
    finally:
        db.close()

    prices = client.get("/api/v1/market/prices")
    assert prices.status_code == 200, prices.text
    body = prices.json()
    assert body["data_state"] == "cached"
    assert body["prices"][0]["modal_price"] == "5100.00"
    assert body["prices"][0]["is_sample"] is True

    nearby = client.get("/api/v1/market/nearby?latitude=20.15&longitude=74.22&radius_km=50")
    assert nearby.status_code == 200
    assert nearby.json()[0]["name"] == "Lasalgaon"
