# Krushi Seva — Weather Foundation (Step 7)

> Scope: location-based weather DATA (current + 7-day forecast) with caching.
> NO advisory, recommendations, alerts engine, or AI — Step 7 measures only.

## 1. Weather architecture

```
Farm GPS (or explicit lat/lon)
  → weather.service (owns flow: validate → cache → provider → persist)
      → WeatherProvider (ABC — service depends ONLY on this)
      │     ├── OpenMeteoProvider (keyless default, httpx)
      │     └── DisabledProvider (fails closed, offline/dev)
      → weather_records (DB cache: snapshots + forecast days)
```

Swapping providers = new `WeatherProvider` subclass + factory entry in
`providers.get_provider()`; service/router/tests need no changes.

## 2. Provider abstraction

`WeatherProvider.get_current_weather(lat, lon) -> CurrentReading` and
`get_forecast(lat, lon, days) -> list[ForecastDay]` — normalized dataclasses
in farmer units already. `ProviderError` carries no secrets and no raw
payloads (safe to log/map to 503). Raw provider JSON is read field-by-field
and discarded — never persisted as the application model. Open-Meteo is
requested with `temperature_unit=celsius&windspeed_unit=kmh&
precipitation_unit=mm&timezone=auto` so units are explicit, never assumed.

## 3. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `WEATHER_PROVIDER` | `open-meteo` | `open-meteo` \| `disabled` (validated, fail-fast) |
| `WEATHER_API_KEY` | (empty) | Reserved for keyed providers; never in code/frontend |
| `WEATHER_API_BASE_URL` | `https://api.open-meteo.com` | Override for proxies/mirrors |
| `WEATHER_TIMEOUT_SECONDS` | `10` | Provider HTTP timeout (fail fast) |
| `WEATHER_CURRENT_TTL_MINUTES` | `30` | Snapshot cache TTL |
| `WEATHER_FORECAST_TTL_HOURS` | `6` | Forecast cache TTL |

Placeholders only in `.env.example`; real keys live in gitignored `.env`.

## 4. API endpoints

| Method & path | Success | Errors |
|---|---|---|
| `GET /api/v1/weather/current?latitude=&longitude=` | 200 + `data_state` | 401 · 422 bad coords · 503 |
| `GET /api/v1/weather/forecast?latitude=&longitude=` | 200, 7 days | 401 · 422 · 503 |
| `GET /api/v1/farms/{id}/weather/current` | 200 (own farm's GPS) | 401 · 404 farm / `FARM_LOCATION_MISSING` · 503 |
| `GET /api/v1/farms/{id}/weather/forecast` | 200 | 401 · 404 · 503 |

Farm endpoints resolve coordinates from the farmer's OWN farm row — never
from client input; foreign farm ids 404 at the farm leg (same anti-IDOR
rule as Steps 4–6). Every response carries `data_state`.

## 5. Location hierarchy

1. Farm GPS (`latitude` + `longitude` both set) → weather served.
2. Farmer profile holds TEXT location only (no coordinates) → documented
   future geocoding hook; today this leg yields `FARM_LOCATION_MISSING`.
3. Nothing → `404 FARM_LOCATION_MISSING` with guidance ("add location").
   GPS is never required or forced. Home dashboard uses the oldest farm
   with GPS; otherwise the unavailable card.

## 6. Caching

DB-backed `weather_records` (no Redis in the project yet — the cache is a
service-level abstraction; a Redis backend can replace the repository
without touching service/router). Coordinates rounded to 4 dp for cache
keys; refresh UPDATES rows in place (no history buildup); dedup enforced by
partial unique indexes. TTLs configurable (30 min current / 6 h forecast).
Freshness evaluated in Python (`coerce_utc`) for SQLite/Postgres parity.

## 7. Units

Backend `units.py` is the single conversion point: °C, km/h, mm, %.
`condition_from_wmo()` maps WMO codes to stable condition keys
(`clear|partly_cloudy|cloudy|fog|drizzle|rain|freezing_rain|storm|snow` —
contract, never renamed); unknown codes degrade to `cloudy`. Frontend
(`weatherLabels.ts`) maps keys → emoji + localized label and formats only.

## 8. Error handling

- `WEATHER_PROVIDER_UNAVAILABLE` (503): provider misconfigured/disabled.
- `WEATHER_DATA_UNAVAILABLE` (503): provider failed AND no cache.
- `INVALID_LOCATION`: 422 via query validation (lat −90…90, lon −180…180).
- `FARM_LOCATION_MISSING` (404): farm has no GPS (+ edit link in UI).
- Provider failures log the exception TYPE only (URLs may carry future
  keys); responses are generic envelopes. Nothing is ever fabricated.

## 9. Provider failure behavior

Fresh cache → served as `cached` (provider untouched). Failure + any cache
→ served as `stale` (explicitly labeled, never silent). Failure + empty
cache → 503, zero rows written. The UI badges Fresh / Cached / Stale /
Unavailable on every card.

## 10. Future weather alerts

`weather_records` already stores everything an alert engine needs
(probability, amount, wind, condition per day). Future: threshold rules per
crop + notification module read these rows — no schema change required.

## 11. Future AI advisory integration

Advisory consumes `WeatherCurrent`/`ForecastDay` shapes (stable contract)
plus farm/crop/activity rows. The safety rule stands: this module MUST NOT
grow "rain expected → don't spray" logic — that belongs to a separate,
verified advisory engine in a later step.
