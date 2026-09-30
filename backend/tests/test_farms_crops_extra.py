"""Farms/crops edge-case tests (SQLite, isolated engine, minimal app).

Covers: farm update validation, negative area, soil upsert + duplicate,
invalid variety linkage, crop status transitions, activity cost tally,
farm-list isolation, and deleted-farm nested-leg 404s.
"""

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
        "farm_name": "Extra Plot",
        "area": "4.000",
        "area_unit": "acre",
        "state": "Maharashtra",
        "district": "Nashik",
    }
    payload.update(overrides)
    response = client.post("/api/v1/farms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _crop(client: TestClient, farm_id: str, **overrides) -> dict:
    payload = {"crop_name": "Cotton", "area": "1", "sowing_date": "2026-06-15"}
    payload.update(overrides)
    response = client.post(f"/api/v1/farms/{farm_id}/crops", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_farm_update_validation_422() -> None:
    client = make_client()
    farm = _farm(client)
    # Negative area on update is rejected, farm unchanged.
    bad = client.put(f"/api/v1/farms/{farm['id']}", json={"area": "-3"})
    assert bad.status_code == 422, bad.text
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
    got = client.get(f"/api/v1/farms/{farm['id']}")
    assert got.json()["area_in_acres"] == 4.0


def test_farm_create_area_negative_422() -> None:
    client = make_client()
    for area in ("-5", "0", "0.000"):
        response = client.post(
            "/api/v1/farms", json={"farm_name": "Bad Plot", "area": area}
        )
        assert response.status_code == 422, (area, response.text)
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_soil_upsert_and_duplicate_409() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Soil Plot")
    created = client.post(
        f"/api/v1/farms/{farm['id']}/soil",
        json={"soil_type": "black", "ph": 7.0},
    )
    assert created.status_code == 201, created.text
    updated = client.put(
        f"/api/v1/farms/{farm['id']}/soil",
        json={"soil_type": "red", "ph": 6.5},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["soil_type"] == "red"
    assert updated.json()["ph"] == "6.5"
    dup = client.post(f"/api/v1/farms/{farm['id']}/soil", json={"soil_type": "red"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "SOIL_ALREADY_EXISTS"


def test_soil_get_missing_404() -> None:
    client = make_client()
    farm = _farm(client, farm_name="No Soil Plot")
    response = client.get(f"/api/v1/farms/{farm['id']}/soil")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOIL_NOT_FOUND"


def test_crop_variety_link_invalid_404() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Variety Plot")
    bad = client.post(
        f"/api/v1/farms/{farm['id']}/crops",
        json={"crop_name": "Wheat", "crop_variety_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert bad.status_code == 404, bad.text
    assert bad.json()["error"]["code"] == "CROP_VARIETY_INVALID"
    missing = client.get("/api/v1/crop-varieties/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CROP_VARIETY_INVALID"


def test_crop_status_transitions() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Status Plot")
    crop = _crop(client, farm["id"])
    assert crop["status"] == "sown"
    for status in ("growing", "harvested"):
        response = client.put(
            f"/api/v1/farms/{farm['id']}/crops/{crop['id']}", json={"status": status}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status
    # Outside the literal union → schema-level 422.
    bad = client.put(
        f"/api/v1/farms/{farm['id']}/crops/{crop['id']}", json={"status": "sprouting"}
    )
    assert bad.status_code == 422, bad.text


def test_crop_harvest_before_sowing_422() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Date Plot")
    response = client.post(
        f"/api/v1/farms/{farm['id']}/crops",
        json={
            "crop_name": "Maize",
            "sowing_date": "2026-07-01",
            "expected_harvest_date": "2026-06-01",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_activities_cost_tally() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Cost Plot")
    crop = _crop(client, farm["id"], crop_name="Soybean")
    base = f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/activities"
    costs = [("Sowing", "500"), ("Fertilizer", "1250.50")]
    for day, (title, cost) in zip(("2026-07-05", "2026-07-12"), costs):
        response = client.post(
            base,
            json={
                "activity_type": "other",
                "title": title,
                "activity_date": day,
                "cost": cost,
            },
        )
        assert response.status_code == 201, response.text
    listed = client.get(base)
    assert listed.status_code == 200
    total = sum(float(a["cost"]) for a in listed.json() if a["cost"] is not None)
    assert total == 1750.50
    timeline = client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()["activities"]) == 2


def test_farm_list_isolation() -> None:
    owner = make_client("farmer-a")
    other = make_client("farmer-b")
    farm = _farm(owner, farm_name="Owner Only Plot")
    mine = owner.get("/api/v1/farms")
    assert mine.status_code == 200
    assert farm["id"] in [f["id"] for f in mine.json()]
    theirs = other.get("/api/v1/farms")
    assert theirs.status_code == 200
    assert all(f["id"] != farm["id"] for f in theirs.json())


def test_deleted_farm_nested_legs_404() -> None:
    client = make_client()
    farm = _farm(client, farm_name="Doomed Plot")
    crop = _crop(client, farm["id"])
    assert client.delete(f"/api/v1/farms/{farm['id']}").status_code == 204
    assert client.get(f"/api/v1/farms/{farm['id']}").status_code == 404
    nested = [
        client.get(f"/api/v1/farms/{farm['id']}/crops"),
        client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}"),
        client.get(f"/api/v1/farms/{farm['id']}/soil"),
        client.post(f"/api/v1/farms/{farm['id']}/crops", json={"crop_name": "X"}),
        client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/timeline"),
    ]
    for response in nested:
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] in (
            "FARM_NOT_FOUND",
            "CROP_NOT_FOUND",
            "SOIL_NOT_FOUND",
        )
