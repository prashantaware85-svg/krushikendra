# Krushi Seva — Crop Activities & Calendar (Step 6)

> Scope: manual activity recording, chronological timeline, simple
> month calendar. NO advisory, recommendations, dosages, or AI — Step 6
> records and displays farmer-entered data only.

## 1. Activity architecture

```
User (auth identity)
 └─ FarmerProfile (1:1)
     └─ Farm (1:N, farmer_id → farmer_profiles.id)
         └─ FarmCrop (1:N, farm_id → farms.id)
             └─ FarmActivity (1:N, farm_crop_id → farm_crops.id)  ← Step 6
                 └─ (future: weather ctx, products, expenses, AI links…)
```

`app/modules/activities/` follows the repo convention (`schemas.py`,
`repository.py`, `service.py`, `router.py`). Auth/farm/crop code untouched —
ownership reuses `crops_service.get_crop` + `farms_service.resolve_farmer_id`.

## 2. Farmer → Farm → Crop → Activity relationship

`farm_activities` carries NO `farmer_id` and NO `farm_id`. Every query JOINs
`farm_activities → farm_crops → farms` with all three `is_active` flags and
the farmer filter, so a row is reachable only through a live crop on a live
farm the caller owns — including manipulated URLs that pair a foreign crop
with an owned farm (the JOIN pins both legs to the same farm).

## 3. Activity types & statuses

Types (open Literal union — new types need no logic change): land_preparation,
sowing, transplanting, irrigation, fertilizer_application,
pesticide_application, fungicide_application, herbicide_application, weeding,
interculture, pruning, scouting, harvesting, other. Statuses: planned (DEFAULT
for manual creates), completed, skipped, cancelled. Both enforced by Pydantic
Literals AND DB CHECKs. Status changes are plain field updates (no workflow
engine); "mark completed" is just `PUT {status: completed}`.

## 4. Date handling

**Decision: single `activity_date` DATE + `status`** (no planned/completed
pair). Rationale: one date keeps manual entry simple; DATE has no timezone
complexity; `planned` = future task, `completed` = work done. A future
`completed_date` can be added later with this column becoming the planned
date — no breakage. `created_at` (UTC) is exposed read-only as "Recorded on".

## 5. API endpoints

| Method & path | Success | Errors |
|---|---|---|
| `GET /api/v1/farms/{fid}/crops/{cid}/activities` | 200 chronological | 401 · 404 farm/crop leg |
| `POST …/activities` | 201 (defaults planned) | 401 · 404 (incl. inactive crop/farm) · 422 |
| `GET …/activities/{aid}` | 200 | 401 · 404 |
| `PUT …/activities/{aid}` | 200 (partial, incl. status flips) | 401 · 404 · 422 |
| `DELETE …/activities/{aid}` | 204 soft delete | 401 · 404 |
| `GET …/crops/{cid}/timeline` | 200 `{farm_id, crop_id, crop_name, activities[]}` | 401 · 404 |

Money/measure as JSON strings (`quantity` NUMERIC(10,3) > 0, `cost`
NUMERIC(12,2) ≥ 0 — money never floats; NULL = not recorded).

## 6. Authorization

Bearer auth; farmer derived server-side; `farm_id`/`crop_id` from path only.
Uniform 404s per leg (`FARM_NOT_FOUND` / `CROP_NOT_FOUND` /
`ACTIVITY_NOT_FOUND`) — no existence oracle, no IDOR. Soft delete preserves
rows for future FKs. Responses carry no `farmer_id`/`is_active`.

## 7. Soft deletion

`is_active=false` on DELETE; list/timeline/get exclude inactive rows;
creation under inactive crop/farm 404s at the ownership legs. Rows retained
for future expense/weather/AI attachments.

## 8. Future integrations (untouched)

`farm_activities.id` anchors: weather context snapshots, product/fertilizer/
pesticide usage rows, labour entries, expense links, AI recommendation refs,
photo/document attachments, irrigation reminders, notifications. The table
needs no changes for these — they attach outward.

## 9. Explicit non-goals (safety)

No generated schedules, no dosage math, no chemical/disease/irrigation
advice anywhere in code, UI, or docs. The calendar renders ONLY what the
farmer recorded.
