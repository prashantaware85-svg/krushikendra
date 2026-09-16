"""Khata ledger schemas (reads only — entries are immutable)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KhataEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_type: str
    amount_paise: int
    balance_after_paise: int
    order_id: UUID | None
    note: str | None
    created_at: datetime


class KhataSummaryOut(BaseModel):
    total_debits_paise: int
    total_credits_paise: int
    total_payments_paise: int
    outstanding_paise: int
    credit_limit_paise: int
    over_limit: bool
    currency: str = "INR"


class KhataEntriesPage(BaseModel):
    entries: list[KhataEntryOut]
    total: int
    limit: int
    offset: int
