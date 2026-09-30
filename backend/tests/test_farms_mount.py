"""Regression: farms routes must resolve through the REAL app mounting.

`app.main.create_app()` mounts `api_router` at `settings.api_v1_prefix`
(`/api/v1`). The farms router must therefore use the short prefix `/farms`
— a full `/api/v1/farms` prefix here double-mounts to
`/api/v1/api/v1/farms` in production while unit tests that include the
router directly keep passing (the exact blind spot behind the /farms 404).

These tests fail if the double prefix ever returns.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  # register all tables on Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.modules.auth import repository
from app.modules.auth.security import create_access_token

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def prod_client():
    """Full production app (real create_app mounting) on throwaway SQLite."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = create_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def _auth_headers() -> dict[str, str]:
    db = TestingSession()
    try:
        user = repository.create_user(db, "9876543210")
        db.commit()
        token, _ = create_access_token(str(user.id), get_settings())
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_list_farms_resolves_at_single_prefix(prod_client: TestClient):
    response = prod_client.get("/api/v1/farms", headers=_auth_headers())
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_no_double_prefixed_farms_route(prod_client: TestClient):
    response = prod_client.get("/api/v1/api/v1/farms", headers=_auth_headers())
    assert response.status_code == 404


def test_openapi_exposes_single_prefix_only(prod_client: TestClient):
    spec = prod_client.get("/openapi.json")
    assert spec.status_code == 200, spec.text
    paths = spec.json()["paths"]
    assert "/api/v1/farms" in paths
    assert "get" in paths["/api/v1/farms"]
    # Farms-router-owned paths must not exist under the double prefix.
    for bad in (
        "/api/v1/api/v1/farms",
        "/api/v1/api/v1/farms/{farm_id}",
        "/api/v1/api/v1/farms/{farm_id}/soil",
    ):
        assert bad not in paths


# ── Same double-prefix class: crops / activities / market / weather ──
# These routers used prefix="/api/v1" while main.py already mounts /api/v1,
# so every route below 404'd in production. They now use prefix="" and the
# decorators carry the full sub-paths.

CROPS_ACTIVITY_MARKET_WEATHER_PATHS = [
    # crops
    "/api/v1/farms/{farm_id}/crops",
    "/api/v1/farms/{farm_id}/crops/{crop_id}",
    "/api/v1/crop-varieties",
    "/api/v1/crop-varieties/{variety_id}",
    # activities
    "/api/v1/farms/{farm_id}/crops/{crop_id}/activities",
    "/api/v1/farms/{farm_id}/crops/{crop_id}/activities/{activity_id}",
    "/api/v1/farms/{farm_id}/crops/{crop_id}/timeline",
    # market
    "/api/v1/market/commodities",
    "/api/v1/market/markets",
    "/api/v1/market/prices",
    "/api/v1/farms/{farm_id}/market-prices",
    # weather
    "/api/v1/weather/current",
    "/api/v1/weather/forecast",
    "/api/v1/farms/{farm_id}/weather/current",
    "/api/v1/farms/{farm_id}/weather/forecast",
]


def test_openapi_single_prefix_for_all_fixed_routers(prod_client: TestClient):
    spec = prod_client.get("/openapi.json")
    assert spec.status_code == 200, spec.text
    paths = spec.json()["paths"]
    for path in CROPS_ACTIVITY_MARKET_WEATHER_PATHS:
        assert path in paths, f"missing single-prefix route {path}"
    doubled = [p for p in paths if p.startswith("/api/v1/api/v1/")]
    assert doubled == [], doubled


def test_global_lists_resolve_live(prod_client: TestClient):
    headers = _auth_headers()
    varieties = prod_client.get("/api/v1/crop-varieties", headers=headers)
    assert varieties.status_code == 200, varieties.text
    assert varieties.json() == []
    commodities = prod_client.get("/api/v1/market/commodities", headers=headers)
    assert commodities.status_code == 200, commodities.text
    assert commodities.json() == []
