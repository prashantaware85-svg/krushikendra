"""Weather cache access. Coordinates are rounded to 4 dp for cache keys."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weather import WeatherRecord


def round_coord(value: float) -> float:
    return round(float(value), 4)


def get_record(db: Session, latitude: float, longitude: float, kind: str) -> WeatherRecord | None:
    return db.scalars(
        select(WeatherRecord)
        .where(
            WeatherRecord.latitude == round_coord(latitude),
            WeatherRecord.longitude == round_coord(longitude),
            WeatherRecord.kind == kind,
        )
        .order_by(WeatherRecord.recorded_at.desc())
    ).first()


def upsert_record(db: Session, **fields) -> WeatherRecord:
    existing = get_record(db, fields["latitude"], fields["longitude"], fields.get("kind", "current"))
    if existing is None:
        record = WeatherRecord(**fields)
        db.add(record)
    else:
        for key, value in fields.items():
            setattr(existing, key, value)
        record = existing
    db.commit()
    db.refresh(record)
    return record
