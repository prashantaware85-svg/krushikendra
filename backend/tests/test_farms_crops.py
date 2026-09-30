"""Farms + crops + activities happy-path, scoping, and soft-delete tests (SQLite)."""

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
from app.modules.activities.router import router as activities_router
from app.modules.auth.dependencies import get_current_user
from app.modules.crops.router import router as crops_router
from app.modules.farms.router import router as farms_router

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
    app.include_router(crops_router)
    app.include_router(activities_router)

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
    payload = {
        "farm_name": "Malegaon Plot",
        "area": "5.000",
        "area_unit": "acre",
        "state": "Maharashtra",
        "district": "Nashik",
        "village": "Malegaon",
        "latitude": 20.5500,
        "longitude": 74.5000,
    }
    payload.update(overrides)
    response = client.post("/api/v1/farms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get_farm_with_soil() -> None:
    client = make_client()
    farm = _farm(client)
    assert farm["farm_name"] == "Malegaon Plot"
    assert farm["area"] == "5.000"
    assert farm["area_in_acres"] == 5.0

    got = client.get(f"/api/v1/farms/{farm['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == farm["id"]

    soil = client.post(
        f"/api/v1/farms/{farm['id']}/soil",
        json={"soil_type": "black", "ph": 7.2, "nitrogen": 280.5, "tested_on": "2026-08-20"},
    )
    assert soil.status_code == 201, soil.text
    assert soil.json()["ph"] == "7.2"

    dup = client.post(f"/api/v1/farms/{farm['id']}/soil", json={"soil_type": "red"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "SOIL_ALREADY_EXISTS"


def test_cross_farmer_farm_returns_404() -> None:
    owner = make_client("farmer-a")
    farm = _farm(owner, farm_name="Private Plot")
    stranger = make_client("farmer-b")
    for method in ("get", "put", "delete"):
        response = getattr(stranger, method)(f"/api/v1/farms/{farm['id']}")
        if method == "put":
            response = stranger.put(f"/api/v1/farms/{farm['id']}", json={"village": "X"})
        assert response.status_code == 404, (method, response.text)
        assert response.json()["error"]["code"] == "FARM_NOT_FOUND"


def test_crop_crud_and_soft_delete() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Crop Plot")
    created = client.post(
        f"/api/v1/farms/{farm['id']}/crops",
        json={"crop_name": "Cotton", "area": "2", "area_unit": "acre", "sowing_date": "2026-06-15"},
    )
    assert created.status_code == 201, created.text
    crop = created.json()
    assert crop["status"] == "sown"

    deleted = client.delete(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}")
    assert deleted.status_code == 204

    gone = client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}")
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "CROP_NOT_FOUND"

    listed = client.get(f"/api/v1/farms/{farm['id']}/crops")
    assert listed.status_code == 200
    assert all(c["id"] != crop["id"] for c in listed.json())


def test_activity_timeline_is_chronological() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Activity Plot")
    crop = client.post(
        f"/api/v1/farms/{farm['id']}/crops",
        json={"crop_name": "Soybean", "area": "1", "sowing_date": "2026-07-01"},
    ).json()
    base = f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/activities"
    for day, title in (("2026-07-20", "Weeding"), ("2026-07-05", "Sowing"), ("2026-07-12", "Irrigation")):
        response = client.post(
            base,
            json={"activity_type": "other", "title": title, "activity_date": day},
        )
        assert response.status_code == 201, response.text
    timeline = client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/timeline")
    assert timeline.status_code == 200
    titles = [a["title"] for a in timeline.json()["activities"]]
    assert titles == ["Sowing", "Irrigation", "Weeding"]
