"""Weather flow: validate → cache → provider → persist (facts only, never fabricated)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import coerce_utc, utcnow
from app.modules.farms import service as farms_service
from app.modules.weather import repository, schemas
from app.modules.weather.providers import (
    CurrentReading,
    DisabledProvider,
    ForecastReading,
    ProviderError,
    WeatherProvider,
    get_provider,
    round_coord,
)


def _ttls() -> tuple[int, int]:
    try:
        from app.core.config import get_settings

        settings = get_settings()
        return settings.weather_current_ttl_minutes, settings.weather_forecast_ttl_hours
    except Exception:
        return 30, 6


def _validate_coords(latitude: Any, longitude: Any) -> tuple[float, float]:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise AppError("Invalid location.", code="INVALID_LOCATION", status_code=422)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise AppError("Invalid location.", code="INVALID_LOCATION", status_code=422)
    return lat, lon


def _is_fresh(recorded_at: datetime | None, ttl: timedelta) -> bool:
    if recorded_at is None:
        return False
    return utcnow() - coerce_utc(recorded_at) <= ttl


def _fmt(value: float | None, decimals: int = 1) -> str | None:
    return None if value is None else f"{value:.{decimals}f}"


def _coord_str(value: float) -> str:
    return f"{round_coord(value):.4f}"


def _current_schema(
    latitude: float,
    longitude: float,
    reading: CurrentReading,
    *,
    data_state: str,
    provider_name: str,
) -> schemas.WeatherCurrent:
    return schemas.WeatherCurrent(
        latitude=_coord_str(latitude),
        longitude=_coord_str(longitude),
        data_state=data_state,  # type: ignore[arg-type]
        provider=provider_name,
        temperature=_fmt(reading.temperature_c),
        feels_like=_fmt(reading.feels_like_c),
        humidity=reading.humidity_pct,
        precipitation_probability=reading.precipitation_probability,
        precipitation_amount=_fmt(reading.precipitation_mm),
        wind_speed=_fmt(reading.wind_speed_kmh),
        wind_direction=reading.wind_direction_deg,
        condition=reading.condition or "cloudy",
        description=reading.description,
        observed_at=reading.observed_at,
    )


def _forecast_schema(
    latitude: float,
    longitude: float,
    reading: ForecastReading,
    *,
    data_state: str,
    provider_name: str,
) -> schemas.WeatherForecast:
    return schemas.WeatherForecast(
        latitude=_coord_str(latitude),
        longitude=_coord_str(longitude),
        data_state=data_state,  # type: ignore[arg-type]
        provider=provider_name,
        days=[
            schemas.ForecastDay(
                date=d.date,
                temp_min=_fmt(d.temp_min_c),
                temp_max=_fmt(d.temp_max_c),
                humidity=d.humidity_pct,
                precipitation_probability=d.precipitation_probability,
                precipitation_amount=_fmt(d.precipitation_mm),
                wind_speed=_fmt(d.wind_speed_kmh),
                condition=d.condition or "cloudy",
                description=d.description,
            )
            for d in reading.days
        ],
    )


def _cached_current(row) -> CurrentReading:
    try:
        payload = json.loads(row.raw_json) if row.raw_json else {}
    except (ValueError, TypeError):
        payload = {}
    data = payload.get("current", {}) if isinstance(payload, dict) else {}
    return CurrentReading(
        temperature_c=data.get("temperature_c", row.temp_c),
        feels_like_c=data.get("feels_like_c"),
        humidity_pct=_as_int(data.get("humidity_pct", row.humidity)),
        precipitation_probability=_as_int(data.get("precipitation_probability")),
        precipitation_mm=data.get("precipitation_mm", row.rainfall_mm),
        wind_speed_kmh=data.get("wind_speed_kmh"),
        wind_direction_deg=_as_int(data.get("wind_direction_deg")),
        condition=data.get("condition", "cloudy"),
        description=data.get("description"),
        observed_at=data.get("observed_at"),
    )


def _cached_forecast(row) -> ForecastReading:
    try:
        payload = json.loads(row.raw_json) if row.raw_json else {}
    except (ValueError, TypeError):
        payload = {}
    from app.modules.weather.providers import ForecastDayData

    days = payload.get("days", []) if isinstance(payload, dict) else []
    return ForecastReading(
        days=[
            ForecastDayData(
                date=str(d.get("date", "")),
                temp_min_c=d.get("temp_min_c"),
                temp_max_c=d.get("temp_max_c"),
                humidity_pct=_as_int(d.get("humidity_pct")),
                precipitation_probability=_as_int(d.get("precipitation_probability")),
                precipitation_mm=d.get("precipitation_mm"),
                wind_speed_kmh=d.get("wind_speed_kmh"),
                condition=d.get("condition", "cloudy"),
                description=d.get("description"),
            )
            for d in days
            if isinstance(d, dict)
        ]
    )


def _as_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _snapshot_current(reading: CurrentReading) -> dict:
    return {
        "current": {
            "temperature_c": reading.temperature_c,
            "feels_like_c": reading.feels_like_c,
            "humidity_pct": reading.humidity_pct,
            "precipitation_probability": reading.precipitation_probability,
            "precipitation_mm": reading.precipitation_mm,
            "wind_speed_kmh": reading.wind_speed_kmh,
            "wind_direction_deg": reading.wind_direction_deg,
            "condition": reading.condition,
            "description": reading.description,
            "observed_at": reading.observed_at,
        }
    }


def _snapshot_forecast(reading: ForecastReading) -> dict:
    return {
        "days": [
            {
                "date": d.date,
                "temp_min_c": d.temp_min_c,
                "temp_max_c": d.temp_max_c,
                "humidity_pct": d.humidity_pct,
                "precipitation_probability": d.precipitation_probability,
                "precipitation_mm": d.precipitation_mm,
                "wind_speed_kmh": d.wind_speed_kmh,
                "condition": d.condition,
                "description": d.description,
            }
            for d in reading.days
        ]
    }


def get_current(
    db: Session, latitude: Any, longitude: Any, provider: WeatherProvider | None = None
) -> schemas.WeatherCurrent:
    lat, lon = _validate_coords(latitude, longitude)
    current_ttl, _ = _ttls()
    prov = provider or get_provider()
    cached = repository.get_record(db, lat, lon, "current")
    if cached is not None and _is_fresh(cached.recorded_at, timedelta(minutes=current_ttl)):
        return _current_schema(lat, lon, _cached_current(cached), data_state="cached", provider_name=prov.name)
    try:
        reading = prov.get_current_weather(lat, lon)
    except ProviderError:
        if isinstance(prov, DisabledProvider):
            raise AppError(
                "Weather provider is unavailable.", code="WEATHER_PROVIDER_UNAVAILABLE", status_code=503
            )
        if cached is not None:
            return _current_schema(lat, lon, _cached_current(cached), data_state="stale", provider_name=prov.name)
        raise AppError("Weather data is unavailable.", code="WEATHER_DATA_UNAVAILABLE", status_code=503)
    repository.upsert_record(
        db,
        latitude=round_coord(lat),
        longitude=round_coord(lon),
        kind="current",
        recorded_at=utcnow(),
        temp_c=reading.temperature_c,
        humidity=reading.humidity_pct,
        rainfall_mm=reading.precipitation_mm,
        raw_json=json.dumps(_snapshot_current(reading)),
    )
    return _current_schema(lat, lon, reading, data_state="fresh", provider_name=prov.name)


def get_forecast(
    db: Session, latitude: Any, longitude: Any, provider: WeatherProvider | None = None
) -> schemas.WeatherForecast:
    lat, lon = _validate_coords(latitude, longitude)
    _, forecast_ttl = _ttls()
    prov = provider or get_provider()
    cached = repository.get_record(db, lat, lon, "forecast")
    if cached is not None and _is_fresh(cached.recorded_at, timedelta(hours=forecast_ttl)):
        return _forecast_schema(lat, lon, _cached_forecast(cached), data_state="cached", provider_name=prov.name)
    try:
        reading = prov.get_forecast(lat, lon, 7)
    except ProviderError:
        if isinstance(prov, DisabledProvider):
            raise AppError(
                "Weather provider is unavailable.", code="WEATHER_PROVIDER_UNAVAILABLE", status_code=503
            )
        if cached is not None:
            return _forecast_schema(lat, lon, _cached_forecast(cached), data_state="stale", provider_name=prov.name)
        raise AppError("Weather data is unavailable.", code="WEATHER_DATA_UNAVAILABLE", status_code=503)
    repository.upsert_record(
        db,
        latitude=round_coord(lat),
        longitude=round_coord(lon),
        kind="forecast",
        recorded_at=utcnow(),
        temp_c=None,
        humidity=None,
        rainfall_mm=None,
        raw_json=json.dumps(_snapshot_forecast(reading)),
    )
    return _forecast_schema(lat, lon, reading, data_state="fresh", provider_name=prov.name)


def _farm_coords(db: Session, user: Any, farm_id: str) -> tuple[float, float]:
    farm = farms_service.resolve_farm(db, user, farm_id)
    if farm.latitude is None or farm.longitude is None:
        raise AppError(
            "This farm has no GPS location yet. Add latitude and longitude to use weather data.",
            code="FARM_LOCATION_MISSING",
            status_code=404,
        )
    return float(farm.latitude), float(farm.longitude)


def get_farm_current(
    db: Session, user: Any, farm_id: str, provider: WeatherProvider | None = None
) -> schemas.WeatherCurrent:
    lat, lon = _farm_coords(db, user, farm_id)
    return get_current(db, lat, lon, provider=provider)


def get_farm_forecast(
    db: Session, user: Any, farm_id: str, provider: WeatherProvider | None = None
) -> schemas.WeatherForecast:
    lat, lon = _farm_coords(db, user, farm_id)
    return get_forecast(db, lat, lon, provider=provider)
