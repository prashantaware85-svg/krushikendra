"""Payment provider abstraction (mock-first).

Only ``mock`` and ``disabled`` exist in this step. The mock provider is
deterministic (reference derived from the idempotency key) and NEVER touches
a real gateway. Production refuses ``mock`` at startup (config guard).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import status

from app.core.config import Settings
from app.core.errors import AppError


@dataclass(frozen=True)
class InitiateResult:
    provider_ref: str
    redirect_url: str
    approved: bool


class MockPaymentProvider:
    """Deterministic dev/test provider, always labelled ``mock``."""

    name = "mock"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def initiate(
        self,
        *,
        order_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        idempotency_key: str,
    ) -> InitiateResult:
        del order_id, amount_paise, currency  # mock needs no gateway fields
        ref = "mock_" + uuid.uuid5(
            uuid.NAMESPACE_URL, f"krushi-seva:{idempotency_key}"
        ).hex[:16]
        approved = self._settings.payment_mock_approve
        return InitiateResult(
            provider_ref=ref,
            redirect_url=(
                f"mock://payments/{ref}?approve={'1' if approved else '0'}"
            ),
            approved=approved,
        )


def get_provider(settings: Settings) -> MockPaymentProvider:
    if settings.payment_provider == "mock":
        return MockPaymentProvider(settings)
    raise AppError(
        "Payment provider is disabled.",
        code="PAYMENT_PROVIDER_DISABLED",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
