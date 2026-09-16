"""Soil-test persistence (CRUD only, no policy)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.soil import SoilTest


def create_test(db: Session, **fields) -> SoilTest:
    row = SoilTest(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save(db: Session, row: SoilTest) -> SoilTest:
    db.commit()
    db.refresh(row)
    return row


def _live(query):
    return query.filter(SoilTest.deleted_at.is_(None))


def list_for_farm(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID
) -> list[SoilTest]:
    return (
        _live(
            db.query(SoilTest).filter(
                SoilTest.farmer_user_id == farmer_id,
                SoilTest.farm_id == farm_id,
            )
        )
        .order_by(SoilTest.tested_on.desc().nullslast(), SoilTest.created_at.desc())
        .all()
    )


def get_owned(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, test_id: uuid.UUID
) -> SoilTest | None:
    """Owner-scoped fetch (None → caller raises uniform 404, no oracle)."""
    return (
        _live(
            db.query(SoilTest).filter(
                SoilTest.id == test_id,
                SoilTest.farmer_user_id == farmer_id,
                SoilTest.farm_id == farm_id,
            )
        ).first()
    )
