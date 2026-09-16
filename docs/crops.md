# Krushi Seva — Crop Management Foundation (Step 5)

> Scope: storing and managing crop plantings + a reference variety
> catalogue. NO advisory, calendar, weather, disease, AI, or market logic —
> Step 5 stores data only.

## 1. Crop architecture

```
User (auth identity)
 └─ FarmerProfile (1:1)
     └─ Farm (1:N, farmer_id → farmer_profiles.id)
         ├─ SoilRecord (1:1)
         └─ FarmCrop (1:N, farm_id → farms.id)      ← Step 5
             └─ (future: calendar, activities, harvest, expenses…)

CropVariety (global catalogue, 1:N ← farm_crops.crop_variety_id, nullable)
```

`app/modules/crops/` follows the repo convention: `schemas.py` contracts,
`repository.py` data access, `service.py` policy, `router.py` thin endpoints.
Area conversion is **reused from Step 4** (`farms.service.to_acres` —
imported, not duplicated). Auth code untouched.

## 2. Crop fields

`farm_crops`: UUID PK; `farm_id` FK → `farms.id` CASCADE (the ONLY ownership
link — no `farmer_id` column by design); `crop_variety_id` FK →
`crop_varieties.id` SET NULL, nullable (NULL = free-text crop, picker
skipped); `crop_name` (64, required); `variety_name` (64, nullable);
`area` NUMERIC(10,3) + `area_unit` (CHECK acre/hectare/guntha) + `area > 0`
CHECK; `season` (CHECK kharif/rabi/zaid/perennial/other); `sowing_date`
DATE required; `expected_harvest_date` DATE nullable with
`harvest >= sowing` CHECK; `status` (CHECK
planned/sown/growing/harvested/failed/cancelled); `notes` TEXT nullable;
`is_active` soft delete; UTC timestamps; indexes on `farm_id`,
`crop_variety_id`, `status`, `is_active`.

`crop_varieties`: UUID PK; `crop_name` (indexed), `variety_name` (nullable —
a NULL-variety row means "any variety"), `crop_category` (indexed free
label: cereal/pulse/oilseed/cash_crop/vegetable/fruit/other — validated at
the API layer, never hard-coded, so new categories need no migration);
`is_active` (inactive rows hidden from pickers and rejected on linking).

## 3. Crop status & seasons

Statuses track a planting's lifecycle (`planned → sown → growing →
harvested`, with `failed`/`cancelled` terminals). Seasons are the Indian
agricultural seasons; a crop is NOT constrained to one season anywhere —
the field is descriptive per planting.

## 4. Area units

Step 4 strategy reused verbatim: original unit stored exactly (NUMERIC),
`to_acres()` converts in Python-Decimal for the `area_in_acres` display
helper. Measurements travel as JSON **strings** (Pydantic v2 default,
precision-safe).

## 5. Crop variety concept

The catalogue is admin-style reference data. The Add Crop form browses
Crop → Variety (datalist + filtered dropdown); picking a variety links
`crop_variety_id` and backfills an empty `variety_name`. Skipping variety is
always valid (`crop_variety_id` NULL). Linking requires the row to exist
AND be active (`CROP_VARIETY_INVALID` 404 otherwise). Deleting a variety
row SETs NULL on plantings (history survives).

## 6. API endpoints

| Method & path | Success | Errors |
|---|---|---|
| `GET /api/v1/farms/{farm_id}/crops` | 200 list (sowing-date order) | 401 · 404 farm leg |
| `POST /api/v1/farms/{farm_id}/crops` | 201 crop | 401 · 404 farm/variety · 422 validation |
| `GET /api/v1/farms/{farm_id}/crops/{crop_id}` | 200 crop | 401 · 404 |
| `PUT /api/v1/farms/{farm_id}/crops/{crop_id}` | 200 updated (dates re-checked vs stored row) | 401 · 404 · 422 |
| `DELETE /api/v1/farms/{farm_id}/crops/{crop_id}` | 204 soft delete | 401 · 404 |
| `GET /api/v1/crop-varieties` | 200 active catalogue | 401 |
| `GET /api/v1/crop-varieties/{id}` | 200 row | 401 · 404 (missing/inactive) |

## 7. Authorization model

Bearer auth everywhere; `farmer_id` derived server-side (user → profile);
`farm_id` from the path only. Crop queries JOIN through the farmer's live
farm (`farmer_id` + `is_active` on `farms`, `is_active` on `farm_crops`) —
missing / foreign / deleted farms AND crops all return the same 404s
(`FARM_NOT_FOUND` / `CROP_NOT_FOUND`), so neither leg oracles existence
(no IDOR). Cross-farmer create is impossible: creation goes through the
owned-farm lookup first. Responses carry no `farmer_id`/`is_active`.

## 8. Seed data (dev only)

`backend/scripts/seed_crop_varieties.py` — 21 idempotent rows (Cotton,
Soybean, Maize, Wheat, Chickpea, Pigeon Pea, Onion × 3 varieties each).
Run manually from `backend/` against a DEV database; refuses
`ENVIRONMENT=production`. Never auto-runs, never seeds farmer/farm data.
Production catalogue management arrives with the future admin module.

## 9. Future extension points (untouched)

`farm_crops.id` anchors: crop calendar entries, farm activities, weather
links, advisory records, disease/pest observations, harvest logs, expenses,
production records, market/sale lots, profit computation. The farms table
needed zero changes for Step 5 and needs none for these either.
