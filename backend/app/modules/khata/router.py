"""Khata ledger endpoints (read-only: summary + paginated entries)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.modules.auth.dependencies import get_current_user
from app.modules.khata import service
from app.modules.khata.schemas import KhataEntriesPage, KhataSummaryOut

router = APIRouter(prefix="/khata", tags=["khata"])


@router.get("/summary", response_model=KhataSummaryOut)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KhataSummaryOut:
    return service.get_summary(db, current_user)


@router.get("/entries", response_model=KhataEntriesPage)
def list_entries(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KhataEntriesPage:
    return service.list_entries(db, current_user, limit=limit, offset=offset)
