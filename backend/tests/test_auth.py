"""Auth + farmer-profile foundation tests (SQLite StaticPool, get_db override)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.auth import FarmerProfile, OtpVerification, RefreshToken, User
from app.models.system import SystemInfo
from app.api.v1.endpoints import health, health_db
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.modules.auth.router import router as auth_router
from app.modules.farmers.router import router as farmers_router
from fastapi import FastAPI

MOBILE = "9876543210"
MOBILE_2 = "9123456789"

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def build_test_app() -> FastAPI:
    """Minimal app mounting ONLY the auth + farmer foundation.

    Deliberately not app.main.create_app(): sibling domain routers are
    restored in parallel and must not break this foundation suite.
    """
    app = FastAPI(title="Krushi Seva API (auth foundation test)")
    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(health_db.router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(farmers_router, prefix="/api/v1")
    return app


# Auth foundation tables only. The full Base.metadata includes sibling-domain
# models that are restored in parallel (currently inconsistent FKs, e.g.
# farm_activities → missing farm_crops), so create_all is scoped to these.
AUTH_TABLES = [
    User.__table__,
    FarmerProfile.__table__,
    OtpVerification.__table__,
    RefreshToken.__table__,
    SystemInfo.__table__,
]


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=AUTH_TABLES)
    Base.metadata.create_all(bind=engine, tables=AUTH_TABLES)
    app = build_test_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine, tables=AUTH_TABLES)


def _send(client: TestClient, mobile: str = MOBILE):
    return client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile})


def _login(client: TestClient, mobile: str = MOBILE) -> dict:
    send = _send(client, mobile)
    assert send.status_code == 200, send.text
    dev_otp = send.json().get("dev_otp")
    assert dev_otp, "dev_otp must be present in non-production test env"
    verify = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": dev_otp}
    )
    assert verify.status_code == 200, verify.text
    return verify.json()


def test_send_otp_validation_rejects_bad_mobile(client: TestClient):
    for bad in ["12345", "abcdef", "1234567890", "5123456789", "+1 5551234567"]:
        response = client.post("/api/v1/auth/send-otp", json={"mobile_number": bad})
        assert response.status_code == 422, bad


def test_send_otp_accepts_plus91_and_zero_prefixes(client: TestClient):
    assert _send(client, "+919876543210").status_code == 200
    Base.metadata.drop_all(bind=engine, tables=AUTH_TABLES)
    Base.metadata.create_all(bind=engine, tables=AUTH_TABLES)
    assert _send(client, "09876543210").status_code == 200


def test_verify_creates_user_and_returns_tokens(client: TestClient):
    body = _login(client)
    assert body["is_new_user"] is True
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["mobile_number"] == MOBILE
    assert payload["is_verified"] is True
    assert payload["profile"]["preferred_language"] == "en"


def test_verify_wrong_otp_returns_400(client: TestClient):
    assert _send(client).status_code == 200
    response = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": MOBILE, "otp": "000000"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_INVALID"


def test_refresh_rotation_revokes_old_token(client: TestClient):
    body = _login(client)
    first = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert first.status_code == 200, first.text
    rotated = first.json()
    assert rotated["refresh_token"] != body["refresh_token"]

    reuse = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "AUTH_INVALID_REFRESH"


def test_logout_is_idempotent(client: TestClient):
    body = _login(client)
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}
        ).status_code
        == 200
    )
    # Second logout with the same (now revoked) token still succeeds.
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}
        ).status_code
        == 200
    )
    # Logged-out refresh token no longer rotates.
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
        ).status_code
        == 401
    )


def test_dev_otp_never_exposed_in_production(client: TestClient, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    response = _send(client, MOBILE_2)
    # Production without a configured SMS provider fails closed: no silent
    # no-delivery success and no dev_otp leak.
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "SMS_NOT_CONFIGURED"
    assert response.json().get("dev_otp") is None


def test_get_current_user_returns_401_without_or_with_bad_token(client: TestClient):
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"].startswith("AUTH_")

    bad = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"].startswith("AUTH_")


def test_farmer_profile_roundtrip_and_validation(client: TestClient):
    body = _login(client)
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    current = client.get("/api/v1/farmer/profile", headers=headers)
    assert current.status_code == 200, current.text

    assert client.get("/api/v1/farmer/profile").status_code == 401

    bad_lang = client.put(
        "/api/v1/farmer/profile", json={"preferred_language": "xx"}, headers=headers
    )
    assert bad_lang.status_code == 422

    empty_name = client.put(
        "/api/v1/farmer/profile", json={"full_name": "   "}, headers=headers
    )
    assert empty_name.status_code == 422

    updated = client.put(
        "/api/v1/farmer/profile",
        json={"full_name": "Test Farmer", "preferred_language": "mr", "village": "Shirur"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["full_name"] == "Test Farmer"
    assert payload["preferred_language"] == "mr"
    assert payload["village"] == "Shirur"
