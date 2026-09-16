"""Weather provider abstraction (service depends ONLY on ``WeatherProvider``).

- ``OpenMeteoProvider``: keyless default, explicit units
  (``temperature_unit=celsius&windspeed_unit=kmh&precipitation_unit=mm``).
- ``MockProvider``: deterministic labelled readings for tests/offline dev.
- ``DisabledProvider``: fails closed (no network, no fabrication).

Swapping sources = new subclass + factory entry; service/router untouched.
Raw provider payloads are read field-by-field and discarded — the
application model is the normalized dataclasses below.
"""

from __future__ import annotations

import abc
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("krushi-seva")


class ProviderError(Exception):
    """Provider failure. Carries no secrets and no raw payloads."""


@dataclass
class CurrentReading:
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_pct: int | None = None
    precipitation_probability: int | None = None
    precipitation_mm: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: int | None = None
    condition: str = "cloudy"
    description: str | None = None
    observed_at: str | None = None


@dataclass
class ForecastDayData:
    date: str = ""
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_pct: int | None = None
    precipitation_probability: int | None = None
    precipitation_mm: float | None = None
    wind_speed_kmh: float | None = None
    condition: str = "cloudy"
    description: str | None = None


@dataclass
class ForecastReading:
    days: list[ForecastDayData] = field(default_factory=list)


_WMO_MAP: dict[int, str] = {
    0: "clear",
    1: "clear",
    2: "partly_cloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "freezing_rain",
    57: "freezing_rain",
    61: "rain",
    63: "rain",
    65: "rain",
    66: "freezing_rain",
    67: "freezing_rain",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "rain",
    81: "rain",
    82: "rain",
    85: "snow",
    86: "snow",
    95: "storm",
    96: "storm",
    99: "storm",
}


def round_coord(value: float) -> float:
    """Round a coordinate to 4 dp for cache keys."""
    return round(float(value), 4)


def condition_from_wmo(code: int | None) -> str:
    """Map a WMO weather code to a stable condition key (unknown → cloudy)."""
    if code is None:
        return "cloudy"
    try:
        return _WMO_MAP.get(int(code), "cloudy")
    except (ValueError, TypeError):
        return "cloudy"


class WeatherProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def get_current_weather(self, latitude: float, longitude: float) -> CurrentReading:
        raise NotImplementedError

    @abc.abstractmethod
    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> ForecastReading:
        raise NotImplementedError


class DisabledProvider(WeatherProvider):
    """Fails closed: offline/dev with no source configured."""

    name = "disabled"

    def get_current_weather(self, latitude: float, longitude: float) -> CurrentReading:
        raise ProviderError("Weather provider is disabled.")

    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> ForecastReading:
        raise ProviderError("Weather provider is disabled.")


class MockProvider(WeatherProvider):
    """Deterministic labelled readings (tests / offline dev only)."""

    name = "mock"

    def get_current_weather(self, latitude: float, longitude: float) -> CurrentReading:
        return CurrentReading(
            temperature_c=30.5,
            feels_like_c=32.0,
            humidity_pct=55,
            precipitation_probability=10,
            precipitation_mm=0.0,
            wind_speed_kmh=12.5,
            wind_direction_deg=180,
            condition="partly_cloudy",
            description="Mock reading (dev/test only)",
            observed_at=None,
        )

    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> ForecastReading:
        from datetime import date as _date, timedelta as _td

        today = _date.today()
        return ForecastReading(
            days=[
                ForecastDayData(
                    date=(today + _td(days=i)).isoformat(),
                    temp_min_c=22.0 + i,
                    temp_max_c=31.0 + i,
                    humidity_pct=55,
                    precipitation_probability=10,
                    precipitation_mm=0.0,
                    wind_speed_kmh=10.0,
                    condition="partly_cloudy",
                    description="Mock forecast (dev/test only)",
                )
                for i in range(max(1, min(days, 7)))
            ]
        )


class OpenMeteoProvider(WeatherProvider):
    """Keyless Open-Meteo provider with explicit units and fail-fast timeout."""

    name = "open-meteo"

    def __init__(self, base_url: str = "https://api.open-meteo.com", timeout_seconds: int = 10):
        self.base_url = (base_url or "https://api.open-meteo.com").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get(self, params: dict) -> dict:
        import httpx

        try:
            response = httpx.get(
                f"{self.base_url}/v1/forecast", params=params, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # network/HTTP/JSON — log type only
            logger.warning("Open-Meteo request failed (%s)", type(exc).__name__)
            raise ProviderError("Weather provider request failed.") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Weather provider returned an invalid payload.")
        return payload

    def get_current_weather(self, latitude: float, longitude: float) -> CurrentReading:
        payload = self._get(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
                ),
                "temperature_unit": "celsius",
                "windspeed_unit": "kmh",
                "precipitation_unit": "mm",
                "timezone": "auto",
            }
        )
        current = payload.get("current") or {}
        code = current.get("weather_code")
        return CurrentReading(
            temperature_c=_num(current.get("temperature_2m")),
            feels_like_c=_num(current.get("apparent_temperature")),
            humidity_pct=_int(current.get("relative_humidity_2m")),
            precipitation_probability=None,
            precipitation_mm=_num(current.get("precipitation")),
            wind_speed_kmh=_num(current.get("wind_speed_10m")),
            wind_direction_deg=_int(current.get("wind_direction_10m")),
            condition=condition_from_wmo(code),
            description=None,
            observed_at=current.get("time"),
        )

    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> ForecastReading:
        payload = self._get(
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,precipitation_sum,"
                    "weathercode,windspeed_10m_max"
                ),
                "temperature_unit": "celsius",
                "windspeed_unit": "kmh",
                "precipitation_unit": "mm",
                "timezone": "auto",
                "forecast_days": max(1, min(days, 7)),
            }
        )
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        out: list[ForecastDayData] = []
        for i, day in enumerate(dates):
            out.append(
                ForecastDayData(
                    date=str(day),
                    temp_min_c=_at(daily.get("temperature_2m_min"), i),
                    temp_max_c=_at(daily.get("temperature_2m_max"), i),
                    humidity_pct=None,
                    precipitation_probability=_int_at(
                        daily.get("precipitation_probability_max"), i
                    ),
                    precipitation_mm=_at(daily.get("precipitation_sum"), i),
                    wind_speed_kmh=_at(daily.get("windspeed_10m_max"), i),
                    condition=condition_from_wmo(_int_at(daily.get("weathercode"), i)),
                    description=None,
                )
            )
        return ForecastReading(days=out)


def _num(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _at(values, index: int) -> float | None:
    if isinstance(values, (list, tuple)) and 0 <= index < len(values):
        return _num(values[index])
    return None


def _int_at(values, index: int) -> int | None:
    if isinstance(values, (list, tuple)) and 0 <= index < len(values):
        return _int(values[index])
    return None


def get_provider(name: str | None = None) -> WeatherProvider:
    """Factory. ``mock`` is honoured from the environment without touching
    ``Settings`` (whose validator only allows the deployed names)."""
    raw = (name or os.getenv("WEATHER_PROVIDER") or _configured_name()).strip().lower()
    if raw == "mock":
        return MockProvider()
    if raw == "disabled":
        return DisabledProvider()
    base_url, timeout = _open_meteo_opts()
    return OpenMeteoProvider(base_url=base_url, timeout_seconds=timeout)


def _configured_name() -> str:
    try:
        from app.core.config import get_settings

        return get_settings().weather_provider
    except Exception:
        return "disabled"


def _open_meteo_opts() -> tuple[str, int]:
    try:
        from app.core.config import get_settings

        settings = get_settings()
        return settings.weather_api_base_url, settings.weather_timeout_seconds
    except Exception:
        return "https://api.open-meteo.com", 10
