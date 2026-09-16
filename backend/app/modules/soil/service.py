"""Soil-test policy: farmer-provided records (+ report files), newest-first.

Report bytes are served solely through the authed report route (no public
URLs). Re-upload replaces (old file removed); delete removes the file
best-effort while the row soft-deletes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.soil import SoilTest
from app.modules.common.storage import LocalFileStorage
from app.modules.soil import repository
from app.modules.soil.reports import REPORT_MEDIA_TYPES, validate_report_bytes

_NUMERIC_FIELDS = (
    "ph",
    "electrical_conductivity",
    "organic_carbon",
    "nitrogen",
    "phosphorus",
    "potassium",
    "sulphur",
    "zinc",
    "iron",
    "manganese",
    "copper",
    "boron",
)


def _storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().soil_storage_dir)


def _not_found() -> AppError:
    return AppError(
        "Soil test not found.",
        code="SOIL_TEST_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _serialize(row: SoilTest) -> dict:
    data: dict = {
        "id": row.id,
        "farm_id": row.farm_id,
        "test_date": row.tested_on,
        "laboratory_name": row.laboratory_name or row.lab_name,
        "report_number": row.report_number,
        "soil_type": row.soil_type,
        "notes": row.notes,
        "has_report": bool(row.report_file_path),
    }
    for field in _NUMERIC_FIELDS:
        value = getattr(row, field)
        data[field] = None if value is None else str(value)
    return data


def list_tests(db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID) -> list[dict]:
    """Newest-first history for one owned farm."""
    return [_serialize(row) for row in repository.list_for_farm(db, farmer_id=farmer_id, farm_id=farm_id)]


def create_test(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, payload: dict
) -> dict:
    """Record farmer-provided values exactly as reported (never converted)."""
    row = repository.create_test(
        db,
        farmer_user_id=farmer_id,
        farm_id=farm_id,
        tested_on=payload.get("test_date"),
        lab_name=payload.get("laboratory_name"),
        laboratory_name=payload.get("laboratory_name"),
        report_number=payload.get("report_number"),
        soil_type=payload.get("soil_type"),
        notes=payload.get("notes"),
        **{f: payload.get(f) for f in _NUMERIC_FIELDS},
    )
    return _serialize(row)


def get_test(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, test_id: uuid.UUID
) -> dict:
    row = repository.get_owned(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    if row is None:
        raise _not_found()
    return _serialize(row)


def update_test(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, test_id: uuid.UUID, patch: dict
) -> dict:
    """Patch provided fields (records stay verbatim; no advice computed)."""
    row = repository.get_owned(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    if row is None:
        raise _not_found()
    if "test_date" in patch:
        row.tested_on = patch["test_date"]
    for field in ("laboratory_name", "report_number", "soil_type", "notes"):
        if field in patch:
            setattr(row, field, patch[field])
    if "laboratory_name" in patch:
        row.lab_name = patch["laboratory_name"]
    for field in _NUMERIC_FIELDS:
        if field in patch:
            setattr(row, field, patch[field])
    return _serialize(repository.save(db, row))


def delete_test(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, test_id: uuid.UUID
) -> None:
    """Soft-delete (``deleted_at``); report file removed best-effort."""
    row = repository.get_owned(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    if row is None:
        raise _not_found()
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    _storage().delete(row.report_file_path)


def upload_report(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    test_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> dict:
    """Validate (magic bytes + size cap) and attach a report (replaces old)."""
    row = repository.get_owned(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    if row is None:
        raise _not_found()
    kind = validate_report_bytes(data, max_mb=get_settings().soil_report_max_mb)
    storage = _storage()
    reference = storage.save_bytes(data, f".{kind}")
    storage.delete(row.report_file_path)  # re-upload replaces the old file
    row.report_file_path = reference
    return _serialize(repository.save(db, row))


def get_report_bytes(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, test_id: uuid.UUID
) -> tuple[bytes, str]:
    """Owned report bytes (authed route only — ``has_report`` elsewhere)."""
    row = repository.get_owned(db, farmer_id=farmer_id, farm_id=farm_id, test_id=test_id)
    if row is None or not row.report_file_path:
        raise AppError(
            "Soil report not found.",
            code="REPORT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    data = _storage().read_bytes(row.report_file_path)
    if data is None:
        raise AppError(
            "Soil report file is no longer available.",
            code="REPORT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    suffix = row.report_file_path.rsplit(".", 1)[-1].lower()
    return data, REPORT_MEDIA_TYPES.get(suffix, "application/octet-stream")
