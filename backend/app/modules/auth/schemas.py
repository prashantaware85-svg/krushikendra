"""Auth request/response contracts (Pydantic v2). Never leaks hashes/secrets."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    mobile_number: str = Field(min_length=1, max_length=20)


class SendOtpResponse(BaseModel):
    message: str
    mobile_number: str
    resend_after_seconds: int
    dev_otp: str | None = None


class VerifyOtpRequest(BaseModel):
    mobile_number: str = Field(min_length=1, max_length=20)
    otp: str = Field(min_length=1, max_length=8)


class VerifyOtpResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    is_new_user: bool


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully."
