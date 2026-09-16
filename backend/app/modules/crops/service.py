"""Crop policy: farm-leg scoping first, then crop-leg; variety linking validated."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.crop import FarmCrop
from app.modules.crops import repository, schemas
from app.modules.farms import service as farms_service
from app.modules.farms.service import acres_to_unit, to_acres


def _uid(user: Any) -> str:
    return str(user.id)


def _parse_date(value: date | str | None, *, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)


def _check_harvest(sowing: date | None, harvest: date | None) -> None:
    if sowing and harvest and harvest < sowing:
        raise AppError(
            "expected_harvest_date cannot be before sowing_date.",
            code="VALIDATION_ERROR",
            status_code=422,
        )


def _resolve_variety_id(db: Session, payload) -> uuid.UUID | None:
    raw = payload.crop_variety_id or payload.variety_id
    if not raw:
        return None
    try:
        variety_id = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        raise AppError("Crop variety is invalid.", code="CROP_VARIETY_INVALID", status_code=404)
    variety = repository.get_variety(db, variety_id)
    if variety is None:
        raise AppError("Crop variety is invalid.", code="CROP_VARIETY_INVALID", status_code=404)
    return variety.id


def to_crop_read(crop: FarmCrop) -> schemas.CropRead:
    acres = crop.area_acres or 0.0
    unit = crop.area_unit or "acre"
    return schemas.CropRead(
        id=str(crop.id),
        farm_id=str(crop.farm_id),
        crop_variety_id=str(crop.crop_variety_id) if crop.crop_variety_id else None,
        crop_name=crop.crop_name,
        variety_name=crop.variety_name,
        area=f"{acres_to_unit(acres, unit):.3f}",
        area_unit=unit,
        area_in_acres=round(float(acres), 3),
        season=crop.season,
        sowing_date=crop.sowing_date.isoformat() if crop.sowing_date else None,
        expected_harvest_date=(
            crop.expected_harvest_date.isoformat() if crop.expected_harvest_date else None
        ),
        status=crop.status,
        notes=crop.notes,
    )


def to_variety_read(variety) -> schemas.CropVarietyRead:
    return schemas.CropVarietyRead(
        id=str(variety.id),
        crop_name=variety.crop_name,
        variety_name=variety.variety_name,
        crop_category=variety.crop_category,
        duration_days=variety.duration_days,
        season=variety.season,
    )


def resolve_crop(db: Session, user: Any, farm_id: str, crop_id: str) -> FarmCrop:
    """Farm leg first (FARM_NOT_FOUND), then crop leg (CROP_NOT_FOUND)."""
    farm = farms_service.resolve_farm(db, user, farm_id)
    crop = repository.get_crop(
        db,
        farms_service.parse_uuid(crop_id, code="CROP_NOT_FOUND", message="Crop not found."),
        farm.id,
        _uid(user),
    )
    if crop is None:
        raise AppError("Crop not found.", code="CROP_NOT_FOUND", status_code=404)
    return crop


def list_crops(db: Session, user: Any, farm_id: str) -> list[schemas.CropRead]:
    farm = farms_service.resolve_farm(db, user, farm_id)
    return [to_crop_read(c) for c in repository.list_crops(db, farm.id, _uid(user))]


def create_crop(db: Session, user: Any, farm_id: str, payload: schemas.CropCreate) -> schemas.CropRead:
    farm = farms_service.resolve_farm(db, user, farm_id)
    if not (payload.crop_name or "").strip():
        raise AppError("crop_name is required.", code="VALIDATION_ERROR", status_code=422)
    variety_id = _resolve_variety_id(db, payload)
    sowing = _parse_date(payload.sowing_date, field="sowing_date")
    harvest = _parse_date(payload.expected_harvest_date, field="expected_harvest_date")
    _check_harvest(sowing, harvest)
    area_acres = farms_service._resolve_area_acres(payload.area, payload.area_acres, payload.area_unit)
    crop = repository.create_crop(
        db,
        farm_id=farm.id,
        crop_variety_id=variety_id,
        crop_name=payload.crop_name.strip(),
        variety_name=payload.variety_name,
        sowing_date=sowing,
        expected_harvest_date=harvest,
        area_acres=area_acres,
        area_unit=payload.area_unit,
        season=payload.season,
        status=payload.status,
        notes=payload.notes,
    )
    return to_crop_read(crop)


def get_crop_detail(db: Session, user: Any, farm_id: str, crop_id: str) -> schemas.CropRead:
    return to_crop_read(resolve_crop(db, user, farm_id, crop_id))


def update_crop(
    db: Session, user: Any, farm_id: str, crop_id: str, payload: schemas.CropUpdate
) -> schemas.CropRead:
    crop = resolve_crop(db, user, farm_id, crop_id)
    data = payload.model_dump(exclude_unset=True)
    patch: dict = {}
    if "crop_name" in data and data["crop_name"] is not None:
        if not data["crop_name"].strip():
            raise AppError("crop_name cannot be empty.", code="VALIDATION_ERROR", status_code=422)
        patch["crop_name"] = data["crop_name"].strip()
    if "crop_variety_id" in data or "variety_id" in data:
        patch["crop_variety_id"] = _resolve_variety_id(db, payload)
        if "variety_name" not in data:
            patch["variety_name"] = crop.variety_name
    for field in ("variety_name", "season", "status", "notes"):
        if field in data:
            patch[field] = data[field]
    sowing = _parse_date(data["sowing_date"], field="sowing_date") if "sowing_date" in data else crop.sowing_date
    harvest = (
        _parse_date(data["expected_harvest_date"], field="expected_harvest_date")
        if "expected_harvest_date" in data
        else crop.expected_harvest_date
    )
    _check_harvest(sowing, harvest)
    if "sowing_date" in data:
        patch["sowing_date"] = sowing
    if "expected_harvest_date" in data:
        patch["expected_harvest_date"] = harvest
    if "area_unit" in data and data["area_unit"] is not None:
        patch["area_unit"] = data["area_unit"]
    if "area" in data or "area_acres" in data:
        patch["area_acres"] = farms_service._resolve_area_acres(
            data.get("area"), data.get("area_acres"), patch.get("area_unit", crop.area_unit or "acre")
        )
    crop = repository.update_crop(db, crop, patch)
    return to_crop_read(crop)


def delete_crop(db: Session, user: Any, farm_id: str, crop_id: str) -> None:
    repository.soft_delete_crop(db, resolve_crop(db, user, farm_id, crop_id))


def list_varieties(db: Session) -> list[schemas.CropVarietyRead]:
    return [to_variety_read(v) for v in repository.list_varieties(db)]


def get_variety_detail(db: Session, variety_id: str) -> schemas.CropVarietyRead:
    variety = repository.get_variety(
        db,
        farms_service.parse_uuid(
            variety_id, code="CROP_VARIETY_INVALID", message="Crop variety not found."
        ),
    )
    if variety is None:
        raise AppError("Crop variety not found.", code="CROP_VARIETY_INVALID", status_code=404)
    return to_variety_read(variety)
