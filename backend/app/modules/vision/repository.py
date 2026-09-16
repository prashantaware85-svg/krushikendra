"""Crop-image persistence (CRUD only, no policy)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.vision import CropImageAnalysis


def create_analysis(db: Session, **fields) -> CropImageAnalysis:
    row = CropImageAnalysis(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save(db: Session, row: CropImageAnalysis) -> CropImageAnalysis:
    db.commit()
    db.refresh(row)
    return row


def list_owned(
    db: Session, *, farmer_id: uuid.UUID, limit: int = 50
) -> list[CropImageAnalysis]:
    return (
        db.query(CropImageAnalysis)
        .filter(
            CropImageAnalysis.farmer_user_id == farmer_id,
            CropImageAnalysis.is_active.is_(True),
        )
        .order_by(CropImageAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )


def get_owned(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID
) -> CropImageAnalysis | None:
    """Owner-scoped fetch (None → caller raises uniform 404, no oracle)."""
    return (
        db.query(CropImageAnalysis)
        .filter(
            CropImageAnalysis.id == analysis_id,
            CropImageAnalysis.farmer_user_id == farmer_id,
            CropImageAnalysis.is_active.is_(True),
        )
        .first()
    )
