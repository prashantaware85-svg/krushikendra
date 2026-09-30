"""Temporary QA OTP test-mode tests (APK testing without real SMS).

Covers the explicit opt-in hook (OTP_TEST_MODE_ENABLED + OTP_TEST_MOBILES):
- allowlisted test number gets dev_otp and can complete login (QA on)
- non-allowlisted numbers never get dev_otp under QA mode
- QA disabled behaves exactly as before (no exposure)
- production defaults never expose OTP and still require a real SMS provider
- half-configured QA (flag on, empty/invalid allowlist) refuses to start
- the Fast2SMS provider path is still invoked for real (non-test) numbers

This hook is TEMPORARY APK QA only: revert the Render env vars after testing.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.auth import FarmerProfile, OtpVerification, RefreshToken, User
from app.models.system import SystemInfo
from app.modules.auth import sms
from app.modules.auth.router import router as auth_router

QA_MOBILE = "9876543210"
OTHER_MOBILE = "9123456789"

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

AUTH_TABLES = [
    User.__table__,
    FarmerProfile.__table__,
    OtpVerification.__table__,
    RefreshToken.__table__,
    SystemInfo.__table__,
]


def build_qa_app() -> FastAPI:
    app = FastAPI(title="Krushi Seva API (OTP QA mode test)")
    register_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    return app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine, tables=AUTH_TABLES)
    Base.metadata.create_all(bind=engine, tables=AUTH_TABLES)
    app = build_qa_app()

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


def _qa_settings(monkeypatch, **overrides) -> object:
    """Enable the QA hook on the cached settings, reverting after the test."""
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_dev_otp_enabled", False)
    monkeypatch.setattr(settings, "otp_test_mode_enabled", True)
    monkeypatch.setattr(settings, "otp_test_mobiles", QA_MOBILE)
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)
    return settings


def _send(client: TestClient, mobile: str = QA_MOBILE):
    return client.post("/api/v1/auth/send-otp", json={"mobile_number": mobile})


def test_qa_allowlisted_mobile_gets_dev_otp_and_can_login(
    client: TestClient, monkeypatch
):
    _qa_settings(monkeypatch)
    send = _send(client, QA_MOBILE)
    assert send.status_code == 200, send.text
    dev_otp = send.json().get("dev_otp")
    assert dev_otp, "allowlisted QA number must receive dev_otp"
    verify = client.post(
        "/api/v1/auth/verify-otp",
        json={"mobile_number": QA_MOBILE, "otp": dev_otp},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["access_token"]


def test_qa_non_allowlisted_mobile_gets_no_dev_otp(
    client: TestClient, monkeypatch
):
    _qa_settings(monkeypatch)
    send = _send(client, OTHER_MOBILE)
    assert send.status_code == 200, send.text
    assert send.json().get("dev_otp") is None


def test_qa_disabled_exposes_nothing(client: TestClient, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_dev_otp_enabled", False)
    monkeypatch.setattr(settings, "otp_test_mode_enabled", False)
    send = _send(client, QA_MOBILE)
    assert send.status_code == 200, send.text
    assert send.json().get("dev_otp") is None


def test_qa_production_allowlisted_gets_dev_otp_without_sms(
    client: TestClient, monkeypatch
):
    """Simulated production + QA flag: allowlisted number works, provider untouched."""
    _qa_settings(monkeypatch, environment="production")

    def _fail_if_called(**kwargs):
        raise AssertionError("provider must be skipped for allowlisted QA numbers")

    monkeypatch.setattr(sms, "send_otp_sms", _fail_if_called)
    send = _send(client, QA_MOBILE)
    assert send.status_code == 200, send.text
    assert send.json().get("dev_otp")


def test_qa_production_non_allowlisted_fails_closed(
    client: TestClient, monkeypatch
):
    """Simulated production + QA flag: real numbers still need a real provider."""
    _qa_settings(monkeypatch, environment="production")
    send = _send(client, OTHER_MOBILE)
    assert send.status_code == 503, send.text
    assert send.json()["error"]["code"] == "SMS_NOT_CONFIGURED"
    assert send.json().get("dev_otp") is None


def test_qa_provider_still_called_for_real_numbers(
    client: TestClient, monkeypatch
):
    """QA flag on: Fast2SMS path is invoked unchanged for non-test numbers."""
    _qa_settings(monkeypatch)
    calls: list[dict] = []

    def _fake_send(**kwargs):
        calls.append(kwargs)
        return "provider-ref-1"

    monkeypatch.setattr(sms, "send_otp_sms", _fake_send)
    send = _send(client, OTHER_MOBILE)
    assert send.status_code == 200, send.text
    assert send.json().get("dev_otp") is None
    assert len(calls) == 1
    assert calls[0]["mobile"] == OTHER_MOBILE
    assert calls[0]["otp"]


def test_qa_mode_requires_allowlist_at_startup():
    with pytest.raises(ValueError, match="OTP_TEST_MOBILES"):
        Settings(otp_test_mode_enabled=True, otp_test_mobiles="")
    with pytest.raises(ValueError, match="OTP_TEST_MOBILES"):
        Settings(otp_test_mode_enabled=True, otp_test_mobiles="not-a-number, ++")


def test_qa_allowlist_normalization():
    settings = Settings(
        otp_test_mobiles="9876543210, +919123456789, junk, 09876543210",
    )
    assert settings.otp_test_mobile_list == ["9876543210", "9123456789"]
    assert Settings().otp_test_mobile_list == []
    assert Settings().otp_test_mode_enabled is False


def test_production_defaults_require_sms_and_never_expose():
    """Standard production config: SMS mandatory, no QA exposure possible."""
    with pytest.raises(ValueError, match="SMS_PROVIDER=fast2sms"):
        Settings(
            environment="production",
            jwt_secret_key="x" * 32,
            auth_dev_otp_enabled=False,
            ai_provider="disabled",
            ai_embedding_provider="disabled",
            vision_provider="disabled",
            payment_provider="disabled",
            sms_provider="disabled",
        )
    prod = Settings(
        environment="production",
        jwt_secret_key="x" * 32,
        auth_dev_otp_enabled=False,
        ai_provider="disabled",
        ai_embedding_provider="disabled",
        vision_provider="disabled",
        payment_provider="disabled",
        sms_provider="fast2sms",
        fast2sms_api_key="test-key",
        fast2sms_otp_id="test-id",
    )
    assert prod.otp_test_mode_enabled is False
    assert prod.otp_test_mobile_list == []
