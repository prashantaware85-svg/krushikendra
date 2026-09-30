"""Farm ownership + scoping tests: cross-farmer 404s, soft-delete, UUIDs (SQLite).

Follows tests/test_farms_crops.py exactly: minimal FastAPI app mounting the
farms/crops/activities routers, module-level StaticPool engine, SimpleNamespace
caller override. Farmer ids are unique per test (shared engine).
"""

import uuid
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


def make_client(user_id: str) -> TestClient:
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


def _uid() -> str:
    return uuid.uuid4().hex


def _farm(client: TestClient, **overrides) -> dict:
    payload = {
        "farm_name": f"Plot {_uid()[:8]}",
        "area": "5.000",
        "area_unit": "acre",
        "state": "Maharashtra",
        "district": "Nashik",
        "village": "Malegaon",
    }
    payload.update(overrides)
    response = client.post("/api/v1/farms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _crop(client: TestClient, farm_id: str, **overrides) -> dict:
    payload = {
        "crop_name": "Cotton",
        "area": "2",
        "area_unit": "acre",
        "sowing_date": "2026-06-15",
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/farms/{farm_id}/crops", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_farmer_crop_returns_404() -> None:
    owner = make_client(f"own-crop-{_uid()}")
    stranger = make_client(f"str-crop-{_uid()}")
    farm = _farm(owner)
    crop = _crop(owner, farm["id"])
    for method, url in (
        ("get", f"/api/v1/farms/{farm['id']}/crops/{crop['id']}"),
        ("get", f"/api/v1/farms/{farm['id']}/crops"),
    ):
        response = getattr(stranger, method)(url)
        assert response.status_code == 404, (method, response.text)
    listed = stranger.get(f"/api/v1/farms/{farm['id']}/crops")
    assert listed.status_code == 404
    assert listed.json()["error"]["code"] == "FARM_NOT_FOUND"
    gone = stranger.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}")
    assert gone.json()["error"]["code"] == "FARM_NOT_FOUND"
    deleted = stranger.delete(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}")
    assert deleted.status_code == 404


def test_cross_farmer_activity_returns_404() -> None:
    owner = make_client(f"own-act-{_uid()}")
    stranger = make_client(f"str-act-{_uid()}")
    farm = _farm(owner)
    crop = _crop(owner, farm["id"])
    activity = owner.post(
        f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/activities",
        json={"activity_type": "other", "title": "Sowing", "activity_date": "2026-07-05"},
    )
    assert activity.status_code == 201, activity.text
    activity_id = activity.json()["id"]
    base = f"/api/v1/farms/{farm['id']}/crops/{crop['id']}"
    for url in (f"{base}/activities", f"{base}/timeline",
                f"{base}/activities/{activity_id}"):
        response = stranger.get(url)
        assert response.status_code == 404, (url, response.text)
    created = stranger.post(
        f"{base}/activities",
        json={"activity_type": "other", "title": "Hack", "activity_date": "2026-07-06"},
    )
    assert created.status_code == 404


def test_cross_farmer_soil_returns_404() -> None:
    owner = make_client(f"own-soil-{_uid()}")
    stranger = make_client(f"str-soil-{_uid()}")
    farm = _farm(owner)
    created = owner.post(
        f"/api/v1/farms/{farm['id']}/soil", json={"soil_type": "black", "ph": 7.0}
    )
    assert created.status_code == 201, created.text
    for method in ("get", "put"):
        if method == "get":
            response = stranger.get(f"/api/v1/farms/{farm['id']}/soil")
        else:
            response = stranger.put(
                f"/api/v1/farms/{farm['id']}/soil", json={"ph": 6.0}
            )
        assert response.status_code == 404, (method, response.text)


def test_farm_list_isolation_between_farmers() -> None:
    farmer_a = make_client(f"list-a-{_uid()}")
    farmer_b = make_client(f"list-b-{_uid()}")
    farm = _farm(farmer_a)
    ids_a = [f["id"] for f in farmer_a.get("/api/v1/farms").json()]
    ids_b = [f["id"] for f in farmer_b.get("/api/v1/farms").json()]
    assert farm["id"] in ids_a
    assert farm["id"] not in ids_b


def test_soft_deleted_farm_hides_everywhere() -> None:
    client = make_client(f"del-{_uid()}")
    farm = _farm(client)
    crop = _crop(client, farm["id"])
    assert client.delete(f"/api/v1/farms/{farm['id']}").status_code == 204
    gone = client.get(f"/api/v1/farms/{farm['id']}")
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "FARM_NOT_FOUND"
    assert all(f["id"] != farm["id"] for f in client.get("/api/v1/farms").json())
    # Nested legs under a deleted farm also report the farm as missing.
    assert client.get(f"/api/v1/farms/{farm['id']}/crops").status_code == 404
    assert client.get(
        f"/api/v1/farms/{farm['id']}/crops/{crop['id']}"
    ).status_code == 404


def test_soft_deleted_crop_hides_from_list_and_detail() -> None:
    client = make_client(f"delcrop-{_uid()}")
    farm = _farm(client)
    keep = _crop(client, farm["id"], crop_name="Wheat", sowing_date="2026-06-20")
    drop = _crop(client, farm["id"], crop_name="Jowar", sowing_date="2026-06-21")
    assert client.delete(f"/api/v1/farms/{farm['id']}/crops/{drop['id']}").status_code == 204
    assert client.get(f"/api/v1/farms/{farm['id']}/crops/{drop['id']}").status_code == 404
    listed = client.get(f"/api/v1/farms/{farm['id']}/crops").json()
    assert [c["id"] for c in listed] == [keep["id"]]


def test_invalid_uuid_returns_404_not_500() -> None:
    client = make_client(f"baduuid-{_uid()}")
    farm = _farm(client)
    bad_farm = client.get("/api/v1/farms/not-a-uuid")
    assert bad_farm.status_code == 404
    assert bad_farm.json()["error"]["code"] == "FARM_NOT_FOUND"
    bad_crop = client.get(f"/api/v1/farms/{farm['id']}/crops/not-a-uuid")
    assert bad_crop.status_code == 404
    assert bad_crop.json()["error"]["code"] == "CROP_NOT_FOUND"
    bad_activity = client.get(
        f"/api/v1/farms/{farm['id']}/crops/{_crop(client, farm['id'])['id']}"
        "/activities/not-a-uuid"
    )
    assert bad_activity.status_code == 404
    assert bad_activity.json()["error"]["code"] == "ACTIVITY_NOT_FOUND"


def test_timeline_orders_chronologically_after_updates() -> None:
    client = make_client(f"time-{_uid()}")
    farm = _farm(client)
    crop = _crop(client, farm["id"], crop_name="Soybean", sowing_date="2026-07-01")
    base = f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/activities"
    first = client.post(
        base, json={"activity_type": "other", "title": "Harvest", "activity_date": "2026-10-01"}
    ).json()
    client.post(
        base, json={"activity_type": "other", "title": "Sowing", "activity_date": "2026-07-05"}
    )
    # Move Harvest earlier than Sowing — timeline must re-sort.
    updated = client.put(
        f"{base}/{first['id']}",
        json={"activity_type": "other", "title": "Harvest", "activity_date": "2026-07-01"},
    )
    assert updated.status_code == 200, updated.text
    timeline = client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/timeline")
    assert timeline.status_code == 200
    assert [a["title"] for a in timeline.json()["activities"]] == ["Harvest", "Sowing"]
    # Deleted activities leave the timeline.
    assert client.delete(f"{base}/{first['id']}").status_code == 204
    timeline = client.get(f"/api/v1/farms/{farm['id']}/crops/{crop['id']}/timeline")
    assert [a["title"] for a in timeline.json()["activities"]] == ["Sowing"]


def test_cross_farmer_farm_update_and_delete_404() -> None:
    owner = make_client(f"own-ud-{_uid()}")
    stranger = make_client(f"str-ud-{_uid()}")
    farm = _farm(owner)
    put = stranger.put(f"/api/v1/farms/{farm['id']}", json={"village": "X"})
    assert put.status_code == 404
    assert put.json()["error"]["code"] == "FARM_NOT_FOUND"
    delete = stranger.delete(f"/api/v1/farms/{farm['id']}")
    assert delete.status_code == 404
    # Owner still sees the untouched farm.
    assert owner.get(f"/api/v1/farms/{farm['id']}").status_code == 200
