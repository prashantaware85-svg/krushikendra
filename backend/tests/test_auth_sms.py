"""SMS OTP delivery tests (Fast2SMS-first, fully mocked — never real SMS).

Conventions mirror test_auth.py: SQLite StaticPool, get_db override, scoped
tables, TestClient. The provider boundary (httpx.post) is monkeypatched in
every configured-provider test; the dev-disabled path asserts httpx.post is
never reachable.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.auth import FarmerProfile, OtpVerification, RefreshToken, User
from app.modules.auth.router import router as auth_router
from app.modules.auth.sms import FAST2SMS_SEND_URL

MOBILE = "9876543210"

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def build_sms_test_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (auth SMS test)")
    register_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    return app


SMS_TABLES = [
    User.__table__,
    FarmerProfile.__table__,
    OtpVerification.__table__,
    RefreshToken.__table__,
]


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=SMS_TABLES)
    Base.metadata.create_all(bind=engine, tables=SMS_TABLES)
    app = build_sms_test_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine, tables=SMS_TABLES)


def _sms_settings() -> Settings:
    return Settings(
        environment="test",
        sms_provider="fast2sms",
        fast2sms_api_key="test-api-key",
        fast2sms_otp_id="test-otp-id",
        auth_dev_otp_enabled=True,
    )


def _use_sms_settings(monkeypatch, settings=None):
    settings = settings or _sms_settings()
    monkeypatch.setattr("app.modules.auth.router.get_settings", lambda: settings)
    return settings


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = (
            payload
            if payload is not None
            else {
                "return": True,
                "request_id": "test-req-1",
                "message": "OTP sent successfully",
            }
        )

    def json(self):
        return self._payload


def test_send_otp_dev_flow_unchanged_when_provider_disabled(client: TestClient, monkeypatch):
    """Default (disabled) provider: dev_otp flow intact, network untouched."""

    def _boom(*args, **kwargs):
        raise AssertionError("real network must never be used with disabled provider")

    monkeypatch.setattr(httpx, "post", _boom)
    send = client.post("/api/v1/auth/send-otp", json={"mobile_number": MOBILE})
    assert send.status_code == 200, send.text
    dev_otp = send.json().get("dev_otp")
    assert dev_otp, "dev_otp must be present in non-production test env"
    verify = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": MOBILE, "otp": dev_otp}
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["access_token"]


def test_send_otp_mocked_provider_success_end_to_end(client: TestClient, monkeypatch):
    """Mocked Fast2SMS success: exact request shape, SENT otp verifies."""
    _use_sms_settings(monkeypatch)
    calls = []

    def _fake_post(url, *, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(httpx, "post", _fake_post)
    send = client.post("/api/v1/auth/send-otp", json={"mobile_number": MOBILE})
    assert send.status_code == 200, send.text
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == FAST2SMS_SEND_URL
    assert call["headers"] == {"Authorization": "test-api-key"}
    assert call["timeout"] == 10
    assert call["json"]["mobile"] == MOBILE
    assert call["json"]["otp_id"] == "test-otp-id"
    sent_otp = call["json"]["otp"]
    assert isinstance(sent_otp, str) and len(sent_otp) == 6 and sent_otp.isdigit()
    assert send.json().get("dev_otp") == sent_otp
    verify = client.post(
        "/api/v1/auth/verify-otp", json={"mobile_number": MOBILE, "otp": sent_otp}
    )
    assert verify.status_code == 200, verify.text


def test_send_otp_provider_timeout_returns_safe_503(client: TestClient, monkeypatch):
    _use_sms_settings(monkeypatch)

    def _timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", _timeout)
    response = client.post("/api/v1/auth/send-otp", json={"mobile_number": MOBILE})
    assert response.status_code == 503, response.text
    body = response.json()
    assert body["error"]["code"] == "SMS_SEND_FAILED"
    assert "dev_otp" not in body


def test_send_otp_provider_rejection_returns_safe_503(client: TestClient, monkeypatch):
    _use_sms_settings(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            200, {"return": False, "status_code": 400, "message": "Invalid OTP ID"}
        ),
    )
    response = client.post("/api/v1/auth/send-otp", json={"mobile_number": MOBILE})
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "SMS_SEND_FAILED"


def test_msg91_selected_fails_closed(client: TestClient, monkeypatch):
    settings = Settings(
        environment="test",
        sms_provider="msg91",
        msg91_auth_key="test-auth-key",
        msg91_template_id="test-template-id",
    )
    _use_sms_settings(monkeypatch, settings)
    response = client.post("/api/v1/auth/send-otp", json={"mobile_number": MOBILE})
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "SMS_PROVIDER_UNAVAILABLE"


def test_production_settings_require_configured_sms():
    base = dict(
        environment="production",
        jwt_secret_key="x" * 32,
        auth_dev_otp_enabled=False,
        ai_provider="disabled",
        ai_embedding_provider="disabled",
        vision_provider="disabled",
        payment_provider="disabled",
    )
    with pytest.raises(ValidationError, match="SMS_PROVIDER"):
        Settings(**base, sms_provider="disabled")
    with pytest.raises(ValidationError, match="FAST2SMS_API_KEY"):
        Settings(**base, sms_provider="fast2sms")
    ok = Settings(
        **base,
        sms_provider="fast2sms",
        fast2sms_api_key="test-api-key",
        fast2sms_otp_id="test-otp-id",
    )
    assert ok.sms_provider == "fast2sms"
