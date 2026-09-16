"""Auth security tests: cooldown, caps, exhaustion, reuse, gating, leaks (SQLite).

Follows tests/test_auth.py exactly: a minimal FastAPI app mounting ONLY the
auth + farmer routers, scoped AUTH_TABLES, real OTP values via dev_otp.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import health, health_db
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.time import utcnow
from app.db.base import Base
from app.db.session import get_db
from app.models.auth import FarmerProfile, OtpVerification, RefreshToken, User
from app.models.system import SystemInfo
from app.modules.auth.router import router as auth_router
from app.modules.farmers.router import router as farmers_router

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def build_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (auth security test)")
    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(health_db.router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(farmers_router, prefix="/api/v1")
    return app


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


def _send(client: TestClient, mobile: str):
    return client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile})


def _login(client: TestClient, mobile: str) -> dict:
    send = _send(client, mobile)
    assert send.status_code == 200, send.text
    dev_otp = send.json().get("dev_otp")
    assert dev_otp, "dev_otp must be present in non-production test env"
    verify = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": dev_otp}
    )
    assert verify.status_code == 200, verify.text
    return verify.json()


def test_otp_cooldown_returns_429(client: TestClient):
    first = _send(client, "9876543210")
    assert first.status_code == 200, first.text
    assert first.json()["resend_after_seconds"] > 0
    second = _send(client, "9876543210")
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "OTP_COOLDOWN"


def test_otp_hourly_cap_returns_429(client: TestClient, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "otp_resend_cooldown_seconds", 0)
    mobile = "9123456780"
    for _ in range(settings.otp_max_sends_per_hour):
        response = _send(client, mobile)
        assert response.status_code == 200, response.text
    capped = _send(client, mobile)
    assert capped.status_code == 429
    assert capped.json()["error"]["code"] == "OTP_RATE_LIMITED"


def test_otp_attempts_exhaustion_returns_429_then_not_found(client: TestClient):
    settings = get_settings()
    mobile = "9123456781"
    assert _send(client, mobile).status_code == 200
    max_attempts = settings.otp_max_attempts
    for i in range(max_attempts - 1):
        response = client.post(
            "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": "000000"}
        )
        assert response.status_code == 400, i
        assert response.json()["error"]["code"] == "OTP_INVALID"
    exhausted = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": "000000"}
    )
    assert exhausted.status_code == 429
    assert exhausted.json()["error"]["code"] == "OTP_ATTEMPTS_EXHAUSTED"
    # Record is gone — even the right code now reports "not found".
    gone = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": "000000"}
    )
    assert gone.status_code == 400
    assert gone.json()["error"]["code"] == "OTP_NOT_FOUND"


def test_consumed_otp_reuse_returns_400(client: TestClient):
    mobile = "9123456782"
    send = _send(client, mobile)
    assert send.status_code == 200
    dev_otp = send.json()["dev_otp"]
    first = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": dev_otp}
    )
    assert first.status_code == 200, first.text
    reuse = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": dev_otp}
    )
    assert reuse.status_code == 400
    assert reuse.json()["error"]["code"] in ("OTP_NOT_FOUND", "OTP_INVALID")


def test_expired_otp_returns_400(client: TestClient):
    mobile = "9123456783"
    send = _send(client, mobile)
    assert send.status_code == 200
    dev_otp = send.json()["dev_otp"]
    with TestingSession() as db:
        row = (
            db.query(OtpVerification)
            .filter(
                OtpVerification.mobile_number == mobile,
                OtpVerification.consumed_at.is_(None),
            )
            .order_by(OtpVerification.created_at.desc())
            .first()
        )
        assert row is not None
        row.expires_at = utcnow() - timedelta(minutes=5)
        db.commit()
    response = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": mobile, "otp": dev_otp}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OTP_EXPIRED"


def test_refresh_reuse_after_rotation_returns_401(client: TestClient):
    body = _login(client, "9123456784")
    rotated = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != body["refresh_token"]
    reuse = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "AUTH_INVALID_REFRESH"


def test_logout_unknown_token_is_idempotent_200(client: TestClient):
    response = client.post(
        "/api/v1/auth/logout", json={"refresh_token": "never-issued-token-value"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Logged out successfully."


def test_refresh_token_as_access_token_returns_401(client: TestClient):
    body = _login(client, "9123456785")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['refresh_token']}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"].startswith("AUTH_")


def test_token_signed_with_wrong_secret_returns_401(client: TestClient):
    import jwt

    body = _login(client, "9123456786")
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    forged = jwt.encode(
        {"sub": me.json()["id"], "type": "access"},
        "wrong-secret-" + "x" * 32,
        algorithm="HS256",
    )
    denied = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert denied.status_code == 401
    assert denied.json()["error"]["code"].startswith("AUTH_")


def test_dev_otp_gating_flag_off_hides_otp(client: TestClient, monkeypatch):
    settings = get_settings()
    assert settings.environment != "production"
    monkeypatch.setattr(settings, "auth_dev_otp_enabled", False)
    try:
        response = _send(client, "9123456787")
        assert response.status_code == 200, response.text
        assert response.json().get("dev_otp") is None
    finally:
        monkeypatch.setattr(settings, "auth_dev_otp_enabled", True)
    response = _send(client, "9123456788")
    assert response.status_code == 200, response.text
    assert response.json().get("dev_otp")


def test_responses_never_leak_hashes_or_secrets(client: TestClient):
    send = _send(client, "9123456789")
    assert send.status_code == 200
    dev_otp = send.json()["dev_otp"]
    verify = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": "9123456789", "otp": dev_otp}
    )
    assert verify.status_code == 200
    body = verify.json()
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert refreshed.status_code == 200
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    blob = json.dumps(
        [send.json(), body, refreshed.json(), me.json()], default=str
    ).lower()
    for leaked in ("otp_hash", "token_hash", "password", "secret", "hash_"):
        assert leaked not in blob, leaked


def test_malformed_authorization_header_returns_401(client: TestClient):
    _login(client, "9000000019")
    assert client.get("/api/v1/auth/me").status_code == 401
    bare = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer"})
    assert bare.status_code == 401
    assert bare.json()["error"]["code"].startswith("AUTH_")
    wrong_scheme = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Token abc123"}
    )
    assert wrong_scheme.status_code == 401


def test_cross_user_profile_isolation(client: TestClient):
    body_a = _login(client, "9000000021")
    body_b = _login(client, "9000000022")
    headers_a = {"Authorization": f"Bearer {body_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {body_b['access_token']}"}
    updated = client.put(
        "/api/v1/farmer/profile",
        json={"full_name": "Farmer A", "village": "Shirur"},
        headers=headers_a,
    )
    assert updated.status_code == 200, updated.text
    other = client.get("/api/v1/farmer/profile", headers=headers_b)
    assert other.status_code == 200, other.text
    assert other.json().get("full_name") != "Farmer A"
    me_a = client.get("/api/v1/auth/me", headers=headers_a).json()
    me_b = client.get("/api/v1/auth/me", headers=headers_b).json()
    assert me_a["id"] != me_b["id"]
    assert me_a["mobile_number"] == "9000000021"
    assert me_b["mobile_number"] == "9000000022"
    assert str(uuid.UUID(me_a["id"])) == me_a["id"]  # real UUID identity
