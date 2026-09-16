"""Khata ledger policy.

- Entries are immutable: this service only appends and reads. No update or
  delete function exists anywhere in this module on purpose.
- No stored mutable balance: ``current_balance`` aggregates on every call;
  ``balance_after_paise`` is a per-row audit snapshot, never a source of truth.
- Only the payments success hook (and future authorized billing steps) may
  append ``payment`` entries; commerce checkout writes ZERO khata rows.
"""

from __future__ import annotations

import uuid

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.models.auth import User
from app.models.khata import KHATA_ENTRY_TYPES, KhataEntry
from app.modules.khata import repository
from app.modules.khata.schemas import (
    KhataEntriesPage,
    KhataEntryOut,
    KhataSummaryOut,
)


def _unprocessable(code: str, message: str) -> AppError:
    return AppError(message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def _signed_delta(entry_type: str, amount_paise: int) -> int:
    if entry_type in ("credit", "payment"):
        return amount_paise
    return -amount_paise


def current_balance(db: Session, farmer_id: uuid.UUID) -> int:
    """Balance = sum(credits + payments) − sum(debits), computed on read."""
    totals = repository.sum_by_type(db, farmer_id)
    return (
        totals.get("credit", 0)
        + totals.get("payment", 0)
        - totals.get("debit", 0)
    )


def append_entry(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    entry_type: str,
    amount_paise: int,
    order_id: uuid.UUID | None = None,
    note: str | None = None,
    commit: bool = True,
) -> KhataEntry:
    """Append one immutable entry. ``commit=False`` lets the payments success
    hook fold the insert into its own atomic transaction."""
    if entry_type not in KHATA_ENTRY_TYPES:
        raise _unprocessable(
            "KHATA_ENTRY_INVALID", f"entry_type must be one of {KHATA_ENTRY_TYPES}."
        )
    if amount_paise <= 0:
        raise _unprocessable("KHATA_ENTRY_INVALID", "amount_paise must be positive.")
    entry = KhataEntry(
        farmer_user_id=farmer_id,
        order_id=order_id,
        entry_type=entry_type,
        amount_paise=amount_paise,
        balance_after_paise=current_balance(db, farmer_id)
        + _signed_delta(entry_type, amount_paise),
        note=note,
        # Python-side microsecond timestamp: server_default func.now() has only
        # second precision on SQLite, which ties entries created in the same
        # second and makes newest-first ordering nondeterministic (UUIDs are
        # random). Explicit value keeps PG/SQLite ordering deterministic.
        created_at=utcnow(),
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def record_debit(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    amount_paise: int,
    order_id: uuid.UUID | None = None,
    note: str | None = None,
    commit: bool = True,
) -> KhataEntry:
    """Record an amount the farmer owes (service-level; no farmer route —
    future authorized billing steps call this, never checkout)."""
    return append_entry(
        db,
        farmer_id=farmer_id,
        entry_type="debit",
        amount_paise=amount_paise,
        order_id=order_id,
        note=note,
        commit=commit,
    )


def record_credit(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    amount_paise: int,
    order_id: uuid.UUID | None = None,
    note: str | None = None,
    commit: bool = True,
) -> KhataEntry:
    return append_entry(
        db,
        farmer_id=farmer_id,
        entry_type="credit",
        amount_paise=amount_paise,
        order_id=order_id,
        note=note,
        commit=commit,
    )


def get_summary(db: Session, user: User) -> KhataSummaryOut:
    totals = repository.sum_by_type(db, user.id)
    debits = totals.get("debit", 0)
    credits = totals.get("credit", 0)
    payments = totals.get("payment", 0)
    outstanding = debits - credits - payments
    limit = get_settings().khata_credit_limit
    return KhataSummaryOut(
        total_debits_paise=debits,
        total_credits_paise=credits,
        total_payments_paise=payments,
        outstanding_paise=outstanding,
        credit_limit_paise=limit,
        over_limit=outstanding > limit,
    )


def list_entries(
    db: Session, user: User, *, limit: int = 20, offset: int = 0
) -> KhataEntriesPage:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    entries = repository.list_entries(db, user.id, limit=limit, offset=offset)
    return KhataEntriesPage(
        entries=[KhataEntryOut.model_validate(e) for e in entries],
        total=repository.count_entries(db, user.id),
        limit=limit,
        offset=offset,
    )
