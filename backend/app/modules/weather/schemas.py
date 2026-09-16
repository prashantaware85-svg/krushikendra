"""Weather Pydantic v2 contracts (mirrors ``WeatherCurrent`` / ``WeatherForecast``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DataState = Literal["fresh", "cached", "stale"]


class WeatherCurrent(BaseModel):
    latitude: str
    longitude: str
    data_state: DataState
    provider: str
    temperature: str | None = None
    feels_like: str | None = None
    humidity: int | None = None
    precipitation_probability: int | None = None
    precipitation_amount: str | None = None
    wind_speed: str | None = None
    wind_direction: int | None = None
    condition: str
    description: str | None = None
    observed_at: str | None = None


class ForecastDay(BaseModel):
    date: str
    temp_min: str | None = None
    temp_max: str | None = None
    humidity: int | None = None
    precipitation_probability: int | None = None
    precipitation_amount: str | None = None
    wind_speed: str | None = None
    condition: str
    description: str | None = None


class WeatherForecast(BaseModel):
    latitude: str
    longitude: str
    data_state: DataState
    provider: str
    days: list[ForecastDay] = Field(default_factory=list)
