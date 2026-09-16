# Krushi Seva — My Farm Module (Step 4)

> Scope: farmer profile use for farm ownership, multiple farms, farm details,
> location, area, soil storage, irrigation. NO crops, advice, or
> recommendations — Step 4 stores data only.

## 1. Farm architecture

```
User (auth identity)
 └─ FarmerProfile (1:1, preferred_language, village…)
     └─ Farm (1:N, farmer_id → farmer_profiles.id)
         ├─ SoilRecord (1:1, farm_id → farms.id, unique)
         └─ (Step 5: crops → farms.id — farms table needs NO changes)
```

`app/modules/farms/` follows the repo convention: `schemas.py` contracts,
`repository.py` data access (every query scoped to one farmer + `is_active`),
`service.py` policy (identity resolution, soft delete, soil singleton,
acre conversion), `router.py` thin endpoints. Auth code untouched — the
module reuses `get_current_user` and `ensure_profile`.

## 2. Database structure

Migration `0003_farms` (`down_revision = 0002_auth_tables`):

**farms** — UUID PK; `farmer_id` FK → `farmer_profiles.id` CASCADE + index;
`farm_name` (128); `area` NUMERIC(10,3) + `area_unit` (CHECK
acre/hectare/guntha) + `area > 0` CHECK; optional `state/district/taluka/
village` (64); optional `latitude` NUMERIC(9,6) / `longitude` NUMERIC(10,6)
with range CHECKs; `land_type`/`soil_type` (32); `irrigation_type`,
`water_source`, `ownership_type` (CHECK enums, nullable); `is_active`
(default true) for soft delete; UTC timestamps.

**soil_records** — UUID PK; `farm_id` FK → `farms.id` CASCADE, **unique**
(one record per farm); `soil_type` (32); `soil_test_available` (bool);
`soil_test_date` (DATE); `ph` NUMERIC(4,2); `organic_carbon` NUMERIC(5,2);
`nitrogen/phosphorus/potassium` NUMERIC(8,2); `soil_test_document_reference`
(256, opaque pointer — no file bytes); UTC timestamps.

## 3. API endpoints

| Method & path | Success | Errors |
|---|---|---|
| `GET /api/v1/farms` | 200 list (own live farms) | 401 |
| `POST /api/v1/farms` | 201 farm | 401 · 422 validation |
| `GET /api/v1/farms/{id}` | 200 farm | 401 · 404 (missing/other/deleted — identical) |
| `PUT /api/v1/farms/{id}` | 200 updated (partial) | 401 · 404 · 422 |
| `DELETE /api/v1/farms/{id}` | 204, `is_active=false` (row kept) | 401 · 404 |
| `GET /api/v1/farms/{id}/soil` | 200 record | 401 · 404 farm or `SOIL_NOT_FOUND` |
| `POST /api/v1/farms/{id}/soil` | 201 record | 401 · 404 farm · 409 `SOIL_ALREADY_EXISTS` · 422 |
| `PUT /api/v1/farms/{id}/soil` | 200 updated (partial) | 401 · 404 · 422 |

Wire format: measurements are JSON **strings** (`"area": "5.000"`) —
Pydantic v2 behaviour, keeps NUMERIC precision end-to-end (frontend parses
for display). `area_in_acres` (float, 3 dp) is a derived display helper.

## 4. Area units

Stored unit preserved exactly (`acre` | `hectare` | `guntha`); conversion is
Python-Decimal only: 1 hectare = 2.4710538 acre, 1 guntha = 0.025 acre
(1 acre = 40 guntha). `service.to_acres()` is the single conversion point —
reuse it for all future calculations (never float math on areas).

## 5. Location handling

State/district/taluka/village free text (manual entry first-class); GPS fully
optional and independent (lat without lon allowed); ranges validated at both
Pydantic and DB CHECK level. No geocoding or map dependency in Step 4.

## 6. Soil information

One record per farm (POST once → 409 after; PUT for edits; GET 404 when
absent). NULL means "not measured" (never 0). Test date cannot be future.
Document reference is an opaque string (filename/object key/lab ref) —
file upload arrives in a later step if needed. No recommendations derived.

## 7. Irrigation & ownership

Irrigation: `rainfed|drip|sprinkler|flood|mixed|other`; water:
`rain|borewell|well|canal|farm_pond|river|other`; ownership:
`owned|leased|shared|other` — all nullable, strict Literals + DB CHECKs.
No recommendations, no legal-document fields.

## 8. Security rules

- Bearer auth on every route (`get_current_user`, 401 otherwise).
- `farmer_id` derived server-side from the token's user → profile; never
  accepted from the client (no `farmer_id` in any schema or response).
- Repository scoping (`farmer_id` + `is_active` on every farm query) makes
  cross-farmer access structurally impossible; missing/other/deleted all
  return the same 404 (`FARM_NOT_FOUND`) — no existence oracle, no IDOR.
- Soft delete preserves history and keeps future crop FKs valid.
- Responses expose no `farmer_id`, `is_active`, hashes, or DB internals.

## 9. Future extension points (untouched)

- **Step 5 crops:** new `crops` table with `farm_id` FK → `farms.id`;
  farms table needs zero changes (no crop fields by design).
- Soil-driven advisory/fertilizer logic reads `soil_records` as-is.
- Irrigation scheduling, farm documents upload, farm sharing, area
  analytics (sum `to_acres()` per farmer).
