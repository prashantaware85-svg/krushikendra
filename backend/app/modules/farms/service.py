"""Farms policy: identity scoping, validation, soft delete, area conversion.

``to_acres`` is the single area-conversion point (Decimal math only) —
other modules import it, never duplicate it. No diagnosis/advisory logic.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.farm import Farm
from app.modules.farms import repository, schemas

_HECTARE_TO_ACRE = Decimal("2.4710538")
_GUNTHA_TO_ACRE = Decimal("0.025")


def to_acres(area: Decimal, unit: str) -> Decimal:
    """Convert an area in ``unit`` to acres (single conversion point)."""
    if unit == "hectare":
        return area * _HECTARE_TO_ACRE
    if unit == "guntha":
        return area * _GUNTHA_TO_ACRE
    return area


def acres_to_unit(acres: float, unit: str) -> Decimal:
    """Convert acres back to the display ``unit``."""
    value = Decimal(str(acres))
    if unit == "hectare":
        return value / _HECTARE_TO_ACRE
    if unit == "guntha":
        return value / _GUNTHA_TO_ACRE
    return value


def _uid(user: Any) -> str:
    return str(user.id)


def parse_uuid(value: Any, *, code: str, message: str) -> uuid.UUID:
    """Coerce a path id to UUID (SQLite Uuid columns need real UUID objects).

    Invalid values map to the caller's uniform 404 — never a 500, never an
    oracle distinguishing malformed from foreign ids.
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise AppError(message, code=code, status_code=404)


def _decimal(value: Any, *, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)


def _float_or_none(value: Any, *, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        raise AppError(f"Invalid {field}.", code="VALIDATION_ERROR", status_code=422)


def _coord(value: Any, *, field: str, low: float, high: float) -> float | None:
    parsed = _float_or_none(value, field=field)
    if parsed is None:
        return None
    if not (low <= parsed <= high):
        raise AppError(
            f"Invalid {field}: out of range.", code="INVALID_LOCATION", status_code=422
        )
    return parsed


def _resolve_area_acres(area: Any, area_acres: Any, unit: str) -> float | None:
    if area_acres is not None and area_acres != "":
        direct = _decimal(area_acres, field="area_acres")
        if direct is not None and direct <= 0:
            raise AppError("Area must be greater than zero.", code="VALIDATION_ERROR", status_code=422)
        return float(direct) if direct is not None else None
    if area is None or area == "":
        return None
    amount = _decimal(area, field="area")
    if amount is None or amount <= 0:
        raise AppError("Area must be greater than zero.", code="VALIDATION_ERROR", status_code=422)
    return float(to_acres(amount, unit))


def _farm_name_of(payload: schemas.FarmCreate | schemas.FarmUpdate) -> str | None:
    name = (payload.farm_name or payload.name or "").strip()
    return name or None


def to_farm_read(farm: Farm) -> schemas.FarmRead:
    acres = farm.area_acres or 0.0
    unit = farm.area_unit or "acre"
    return schemas.FarmRead(
        id=str(farm.id),
        farm_name=farm.farm_name,
        area=f"{acres_to_unit(acres, unit):.3f}",
        area_unit=unit,
        area_in_acres=round(float(acres), 3),
        state=farm.state,
        district=farm.district,
        taluka=farm.taluka,
        village=farm.village,
        latitude=f"{farm.latitude:.6f}" if farm.latitude is not None else None,
        longitude=f"{farm.longitude:.6f}" if farm.longitude is not None else None,
        land_type=farm.land_type,
        soil_type=farm.soil_type,
        irrigation_type=farm.irrigation_type,
        water_source=farm.water_source,
        ownership_type=farm.ownership_type,
    )


def _num_str(value: float | None) -> str | None:
    return None if value is None else str(value)


def to_soil_read(farm_id: str, record) -> schemas.SoilRead:
    return schemas.SoilRead(
        id=str(record.id),
        farm_id=farm_id,
        soil_type=record.soil_type,
        soil_test_available=bool(record.soil_test_available),
        soil_test_date=record.soil_test_date.isoformat() if record.soil_test_date else None,
        ph=_num_str(record.ph),
        organic_carbon=_num_str(record.organic_carbon),
        nitrogen=_num_str(record.nitrogen),
        phosphorus=_num_str(record.phosphorus),
        potassium=_num_str(record.potassium),
        soil_test_document_reference=record.soil_test_document_reference,
    )


def _soil_fields(payload: schemas.SoilCreate | schemas.SoilUpdate, *, partial: bool) -> dict:
    data = payload.model_dump(exclude_unset=partial)
    out: dict = {}
    if "soil_type" in data:
        out["soil_type"] = data["soil_type"]
    if "soil_test_available" in data and data["soil_test_available"] is not None:
        out["soil_test_available"] = bool(data["soil_test_available"])
    raw_date = data.get("soil_test_date", None)
    if raw_date is None and "tested_on" in data:
        raw_date = data.get("tested_on")
    if "soil_test_date" in data or "tested_on" in data:
        parsed: date | None = None
        if raw_date not in (None, ""):
            if isinstance(raw_date, date):
                parsed = raw_date
            else:
                try:
                    parsed = date.fromisoformat(str(raw_date))
                except ValueError:
                    raise AppError("Invalid soil_test_date.", code="VALIDATION_ERROR", status_code=422)
        out["soil_test_date"] = parsed
    for field in ("ph", "organic_carbon", "nitrogen", "phosphorus", "potassium"):
        if field in data:
            num = _decimal(data[field], field=field)
            out[field] = float(num) if num is not None else None
    if "soil_test_document_reference" in data:
        out["soil_test_document_reference"] = data["soil_test_document_reference"]
    return out


def list_farms(db: Session, user: Any) -> list[schemas.FarmRead]:
    return [to_farm_read(f) for f in repository.list_farms(db, _uid(user))]


def resolve_farm(db: Session, user: Any, farm_id: str) -> Farm:
    """Return the caller's live farm or raise uniform 404 (no oracle)."""
    farm = repository.get_farm(
        db, parse_uuid(farm_id, code="FARM_NOT_FOUND", message="Farm not found."), _uid(user)
    )
    if farm is None:
        raise AppError("Farm not found.", code="FARM_NOT_FOUND", status_code=404)
    return farm


def get_farm_detail(db: Session, user: Any, farm_id: str) -> schemas.FarmRead:
    return to_farm_read(resolve_farm(db, user, farm_id))


def create_farm(db: Session, user: Any, payload: schemas.FarmCreate) -> schemas.FarmRead:
    name = _farm_name_of(payload)
    if not name:
        raise AppError("farm_name is required.", code="VALIDATION_ERROR", status_code=422)
    farm = repository.create_farm(
        db,
        owner_user_id=_uid(user),
        farm_name=name,
        village=payload.village,
        taluka=payload.taluka,
        district=payload.district,
        state=payload.state,
        area_acres=_resolve_area_acres(payload.area, payload.area_acres, payload.area_unit),
        area_unit=payload.area_unit,
        latitude=_coord(payload.latitude, field="latitude", low=-90.0, high=90.0),
        longitude=_coord(payload.longitude, field="longitude", low=-180.0, high=180.0),
        land_type=payload.land_type,
        soil_type=payload.soil_type,
        irrigation_type=payload.irrigation_type,
        water_source=payload.water_source,
        ownership_type=payload.ownership_type,
    )
    return to_farm_read(farm)


def update_farm(db: Session, user: Any, farm_id: str, payload: schemas.FarmUpdate) -> schemas.FarmRead:
    farm = resolve_farm(db, user, farm_id)
    data = payload.model_dump(exclude_unset=True)
    patch: dict = {}
    if "farm_name" in data or "name" in data:
        name = _farm_name_of(payload)
        if name is not None:
            patch["farm_name"] = name
    unit = data.get("area_unit", farm.area_unit)
    if "area_unit" in data and data["area_unit"] is not None:
        patch["area_unit"] = data["area_unit"]
    if "area" in data or "area_acres" in data:
        current_acres_back = (
            float(acres_to_unit(farm.area_acres or 0.0, farm.area_unit or "acre"))
            if farm.area_acres is not None
            else None
        )
        patch["area_acres"] = _resolve_area_acres(
            data.get("area", current_acres_back),
            data.get("area_acres"),
            patch.get("area_unit", farm.area_unit or "acre"),
        )
        if unit is None:
            patch.pop("area_unit", None)
    for field in ("state", "district", "taluka", "village", "land_type", "soil_type",
                  "irrigation_type", "water_source", "ownership_type"):
        if field in data:
            patch[field] = data[field]
    if "latitude" in data:
        patch["latitude"] = _coord(data["latitude"], field="latitude", low=-90.0, high=90.0)
    if "longitude" in data:
        patch["longitude"] = _coord(data["longitude"], field="longitude", low=-180.0, high=180.0)
    farm = repository.update_farm(db, farm, patch)
    return to_farm_read(farm)


def delete_farm(db: Session, user: Any, farm_id: str) -> None:
    repository.soft_delete_farm(db, resolve_farm(db, user, farm_id))


def get_soil_detail(db: Session, user: Any, farm_id: str) -> schemas.SoilRead:
    farm = resolve_farm(db, user, farm_id)
    record = repository.get_soil(db, farm.id)
    if record is None:
        raise AppError("Soil record not found.", code="SOIL_NOT_FOUND", status_code=404)
    return to_soil_read(str(farm.id), record)


def create_soil(db: Session, user: Any, farm_id: str, payload: schemas.SoilCreate) -> schemas.SoilRead:
    farm = resolve_farm(db, user, farm_id)
    if repository.get_soil(db, farm.id) is not None:
        raise AppError("Soil record already exists.", code="SOIL_ALREADY_EXISTS", status_code=409)
    record = repository.create_soil(db, farm_id=farm.id, **_soil_fields(payload, partial=False))
    return to_soil_read(str(farm.id), record)


def update_soil(db: Session, user: Any, farm_id: str, payload: schemas.SoilUpdate) -> schemas.SoilRead:
    farm = resolve_farm(db, user, farm_id)
    record = repository.get_soil(db, farm.id)
    if record is None:
        raise AppError("Soil record not found.", code="SOIL_NOT_FOUND", status_code=404)
    record = repository.update_soil(db, record, _soil_fields(payload, partial=True))
    return to_soil_read(str(farm.id), record)
