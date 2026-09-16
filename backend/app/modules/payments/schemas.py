"""Payment schemas (initiate → webhook/callback)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitiateCreate(BaseModel):
    order_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=80)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    provider: str
    provider_ref: str
    amount_paise: int
    currency: str
    status: str
    idempotency_key: str


class PaymentInitiateOut(PaymentOut):
    redirect_url: str = ""
    approved: bool = False


class PaymentWebhook(BaseModel):
    """Provider callback. Unknown extra fields are preserved verbatim in
    ``raw_callback_json`` for audit."""

    model_config = ConfigDict(extra="allow")

    provider_ref: str
    status: Literal["success", "failed"]
    signature: str | None = None


class PaymentWebhookOut(BaseModel):
    status: str
    order_payment_status: str
    khata_entry_id: UUID | None = None
    duplicate: bool = False
