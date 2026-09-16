"""Khata ledger reads (farmer-scoped)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.khata import KhataEntry


def sum_by_type(db: Session, farmer_id: uuid.UUID) -> dict[str, int]:
    rows = (
        db.execute(
            select(KhataEntry.entry_type, func.sum(KhataEntry.amount_paise))
            .where(KhataEntry.farmer_user_id == farmer_id)
            .group_by(KhataEntry.entry_type)
        ).all()
    )
    return {entry_type: int(total or 0) for entry_type, total in rows}


def count_entries(db: Session, farmer_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(KhataEntry)
        .where(KhataEntry.farmer_user_id == farmer_id)
    )
    return int(db.scalar(stmt) or 0)


def list_entries(
    db: Session, farmer_id: uuid.UUID, *, limit: int, offset: int
) -> list[KhataEntry]:
    stmt = (
        select(KhataEntry)
        .where(KhataEntry.farmer_user_id == farmer_id)
        .order_by(KhataEntry.created_at.desc(), KhataEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())
