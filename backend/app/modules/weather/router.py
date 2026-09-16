"""Weather thin router: explicit coords + own-farm GPS endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db

try:
    from app.modules.auth.dependencies import get_current_user
except ImportError:  # pragma: no cover - fallback when auth is not restored

    def get_current_user():  # type: ignore[no-redef]
        raise AppError("Authentication is unavailable.", code="NOT_AUTHENTICATED", status_code=401)

from app.modules.weather import schemas, service

router = APIRouter(prefix="/api/v1", tags=["weather"])


@router.get("/weather/current", response_model=schemas.WeatherCurrent)
def weather_current(
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.WeatherCurrent:
    return service.get_current(db, latitude, longitude)


@router.get("/weather/forecast", response_model=schemas.WeatherForecast)
def weather_forecast(
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.WeatherForecast:
    return service.get_forecast(db, latitude, longitude)


@router.get("/farms/{farm_id}/weather/current", response_model=schemas.WeatherCurrent)
def farm_weather_current(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.WeatherCurrent:
    return service.get_farm_current(db, current_user, farm_id)


@router.get("/farms/{farm_id}/weather/forecast", response_model=schemas.WeatherForecast)
def farm_weather_forecast(
    farm_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> schemas.WeatherForecast:
    return service.get_farm_forecast(db, current_user, farm_id)
