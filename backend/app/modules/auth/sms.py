"""SMS OTP delivery (Step 3b: Fast2SMS-first provider abstraction).

Scope:
- OTP generation, hashing, expiry, cooldowns and attempt limits stay in
  service.py (server-side, unchanged). This module ONLY delivers an
  already-generated OTP string over a configured provider.
- Provider credentials come ONLY from Settings (environment variables).
  Never log the OTP, API keys, or full mobile numbers (last-4 only).
- Tests monkeypatch the provider boundary — no real SMS ever leaves
  automated tests.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx
from fastapi import status

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger("krushi-seva.auth.sms")

FAST2SMS_SEND_URL = "https://www.fast2sms.com/dev/otp/send"


class SmsSendError(AppError):
    """Safe 503 for SMS delivery failures (user-safe message, no internals)."""

    def __init__(self, message: str = "Could not send OTP. Please try again.") -> None:
        super().__init__(
            message, code="SMS_SEND_FAILED", status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class SmsProvider(Protocol):
    """Provider contract: deliver an OTP to a 10-digit Indian mobile number.

    Returns the provider's message/request id (or None). Raises SmsSendError
    on any delivery failure. Implementations must never log secrets, OTPs,
    or full mobile numbers.
    """

    name: str

    def send_otp(self, *, mobile: str, otp: str, settings: Settings) -> str | None:
        """Send OTP. `mobile` is the normalized 10-digit number."""
        ...


class Fast2SmsProvider:
    """Fast2SMS /dev/otp/send using OUR OTP (server-side generation kept).

    `mobile` is the normalized 10-digit number from security.normalize_mobile
    (exactly what Fast2SMS expects). Expiry/length mirror our OTP policy so
    the provider-side window matches the server-side one.
    """

    name = "fast2sms"

    def send_otp(self, *, mobile: str, otp: str, settings: Settings) -> str | None:
        payload = {
            "mobile": mobile,
            "otp_id": settings.fast2sms_otp_id,
            "otp": otp,
            "otp_expiry": settings.otp_expire_minutes,
            "otp_length": len(otp),
        }
        try:
            response = httpx.post(
                FAST2SMS_SEND_URL,
                headers={"Authorization": settings.fast2sms_api_key},
                json=payload,
                timeout=settings.sms_timeout_seconds,
            )
        except httpx.TransportError as exc:
            logger.warning(
                "Fast2SMS request failed for mobile ending %s: %s",
                mobile[-4:],
                type(exc).__name__,
            )
            raise SmsSendError() from exc
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning(
                "Fast2SMS non-JSON response (http %s) for mobile ending %s",
                response.status_code,
                mobile[-4:],
            )
            raise SmsSendError() from exc
        if not isinstance(data, dict) or data.get("return") is not True:
            message = data.get("message") if isinstance(data, dict) else None
            logger.warning(
                "Fast2SMS rejected OTP send (http %s) for mobile ending %s: %s",
                response.status_code,
                mobile[-4:],
                message,
            )
            raise SmsSendError()
        request_id = data.get("request_id")
        return request_id if isinstance(request_id, str) else None


def get_sms_provider(settings: Settings) -> SmsProvider | None:
    """Return the configured provider, or None when SMS is disabled.

    "msg91" is reserved for a later drop-in behind this same interface —
    selecting it now fails closed at send time.
    """
    if settings.sms_provider == "fast2sms":
        return Fast2SmsProvider()
    if settings.sms_provider == "msg91":
        raise AppError(
            "SMS provider 'msg91' is not integrated yet.",
            code="SMS_PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


def send_otp_sms(*, mobile: str, otp: str, settings: Settings) -> str | None:
    """Deliver an OTP via the configured provider. Test seam: monkeypatch me.

    Returns the provider message id (or None). Raises AppError 503 when SMS
    is unavailable (provider error/timeout, unconfigured in production, or
    reserved-but-unimplemented provider).
    """
    provider = get_sms_provider(settings)
    if provider is None:
        if settings.is_production:
            raise AppError(
                "SMS provider is not configured.",
                code="SMS_NOT_CONFIGURED",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return None
    return provider.send_otp(mobile=mobile, otp=otp, settings=settings)
