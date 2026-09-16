"""Weather + market extra tests: shapes, validation, radius, history (SQLite).

Follows tests/test_weather_market.py exactly: minimal FastAPI app mounting
farms/weather/market routers, module-level StaticPool engine, SimpleNamespace
caller override, MockProvider seam via monkeypatch.
"""

import uuid
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
    app.include_router(farms_router)
    app.include_router(weather_router)
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


def _farm(client: TestClient, **overrides) -> dict:
    payload = {"farm_name": f"WX {uuid.uuid4().hex[:8]}", "area": "3", "area_unit": "acre"}
    payload.update(overrides)
    response = client.post("/api/v1/farms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_market(name_suffix: str, lat: float, lon: float, prices: list[tuple[str, float]]) -> dict:
    """Seed one commodity + one market + dated price rows. Returns ids."""
    suffix = f"{name_suffix}-{uuid.uuid4().hex[:6]}"
    with TestingSession() as db:
        commodity = MarketCommodity(name=f"Soy-{suffix}", category="oilseed", unit="quintal")
        market = Market(
            name=f"Mandi-{suffix}", district="Nashik", state="Maharashtra",
            latitude=lat, longitude=lon,
        )
        db.add_all([commodity, market])
        db.commit()
        db.refresh(commodity)
        db.refresh(market)
        for iso_day, modal in prices:
            y, m, d = (int(p) for p in iso_day.split("-"))
            db.add(
                MarketPrice(
                    commodity_id=commodity.id,
                    market_id=market.id,
                    price_per_quintal=modal,
                    modal_price=modal,
                    min_price=modal - 100,
                    max_price=modal + 100,
                    price_date=date(y, m, d),
                    source="SAMPLE (dev only)",
                    unit="quintal",
                    is_sample=True,
                )
            )
        db.commit()
        return {"commodity_id": str(commodity.id), "market_id": str(market.id)}


def test_forecast_mock_shape_seven_days(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_provider", lambda name=None: MockProvider())
    client = make_client(f"fc-{uuid.uuid4().hex[:8]}")
    response = client.get("/api/v1/weather/forecast?latitude=20.55&longitude=74.5")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "mock"
    assert body["data_state"] == "fresh"
    assert body["latitude"] == "20.5500" and body["longitude"] == "74.5000"
    assert len(body["days"]) == 7
    for day in body["days"]:
        assert day["date"] and day["condition"]
        assert "temp_min" in day and "temp_max" in day


def test_current_mock_field_values(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_provider", lambda name=None: MockProvider())
    client = make_client(f"cc-{uuid.uuid4().hex[:8]}")
    body = client.get("/api/v1/weather/current?latitude=20.55&longitude=74.5").json()
    assert body["temperature"] == "30.5"
    assert body["condition"] == "partly_cloudy"
    assert body["humidity"] == 55
    assert body["provider"] == "mock"


def test_invalid_coordinates_return_422(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_provider", lambda name=None: MockProvider())
    client = make_client(f"bad-{uuid.uuid4().hex[:8]}")
    over = client.get("/api/v1/weather/current?latitude=200&longitude=0")
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "INVALID_LOCATION"
    under = client.get("/api/v1/weather/forecast?latitude=20&longitude=190")
    assert under.status_code == 422
    non_numeric = client.get("/api/v1/weather/current?latitude=abc&longitude=74.5")
    assert non_numeric.status_code == 422
    nearby_bad = client.get("/api/v1/market/nearby?latitude=95&longitude=74.22")
    assert nearby_bad.status_code == 422
    assert nearby_bad.json()["error"]["code"] == "INVALID_LOCATION"


def test_farm_forecast_without_gps_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_provider", lambda name=None: MockProvider())
    client = make_client(f"nogps-{uuid.uuid4().hex[:8]}")
    farm = _farm(client)
    response = client.get(f"/api/v1/farms/{farm['id']}/weather/forecast")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FARM_LOCATION_MISSING"


def test_farm_weather_cross_farmer_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(weather_service, "get_provider", lambda name=None: MockProvider())
    owner = make_client(f"wxown-{uuid.uuid4().hex[:8]}")
    stranger = make_client(f"wxstr-{uuid.uuid4().hex[:8]}")
    farm = _farm(owner, latitude=20.55, longitude=74.5)
    assert owner.get(f"/api/v1/farms/{farm['id']}/weather/current").status_code == 200
    denied = stranger.get(f"/api/v1/farms/{farm['id']}/weather/current")
    assert denied.status_code == 404


def test_nearby_radius_filtering_and_order() -> None:
    client = make_client(f"nb-{uuid.uuid4().hex[:8]}")
    near = _seed_market("near", 20.15, 74.22, [("2026-09-01", 5100.0)])
    far = _seed_market("far", 22.00, 74.22, [("2026-09-01", 5200.0)])  # ~205 km north
    tight = client.get("/api/v1/market/nearby?latitude=20.15&longitude=74.22&radius_km=50")
    assert tight.status_code == 200, tight.text
    tight_ids = [m["id"] for m in tight.json()]
    assert near["market_id"] in tight_ids
    assert far["market_id"] not in tight_ids
    wide = client.get("/api/v1/market/nearby?latitude=20.15&longitude=74.22&radius_km=500")
    assert wide.status_code == 200, wide.text
    wide_body = wide.json()
    assert [m["id"] for m in wide_body].index(near["market_id"]) < [
        m["id"] for m in wide_body
    ].index(far["market_id"])
    assert all(m["distance_km"] is not None for m in wide_body)


def test_price_history_ordering_ascending() -> None:
    client = make_client(f"hist-{uuid.uuid4().hex[:8]}")
    ids = _seed_market(
        "hist", 20.15, 74.22,
        [("2026-09-03", 5300.0), ("2026-09-01", 5100.0), ("2026-09-02", 5200.0)],
    )
    response = client.get(
        f"/api/v1/market/prices/history?commodity_id={ids['commodity_id']}"
    )
    assert response.status_code == 200, response.text
    dates = [p["price_date"] for p in response.json()["prices"]]
    assert dates == sorted(dates)
    assert [p["modal_price"] for p in response.json()["prices"]] == [
        "5100.00", "5200.00", "5300.00",
    ]


def test_history_requires_filter_and_valid_range() -> None:
    client = make_client(f"hr-{uuid.uuid4().hex[:8]}")
    missing = client.get("/api/v1/market/prices/history")
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "HISTORY_FILTER_REQUIRED"
    ids = _seed_market("rng", 20.15, 74.22, [("2026-09-01", 5100.0)])
    flipped = client.get(
        f"/api/v1/market/prices/history?commodity_id={ids['commodity_id']}"
        "&from_date=2026-09-05&to_date=2026-09-01"
    )
    assert flipped.status_code == 422
    assert flipped.json()["error"]["code"] == "HISTORY_INVALID_RANGE"


def test_invalid_uuid_filter_returns_422_and_empty_prices_503() -> None:
    client = make_client(f"flt-{uuid.uuid4().hex[:8]}")
    bad = client.get("/api/v1/market/prices?commodity_id=not-a-uuid")
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
    empty = client.get(f"/api/v1/market/prices?commodity_id={uuid.uuid4()}")
    assert empty.status_code == 503
    assert empty.json()["error"]["code"] == "MARKET_DATA_UNAVAILABLE"
