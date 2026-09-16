# Krushi Seva — Soil Test + Fertilizer Management (Step 11)

> Scope: recording lab soil tests (+ report files) and fertilizer usage.
> NO dosage recommendations, prescriptions, mixing instructions, or any
> agronomic advice — Step 11 stores farmer-provided data only.

## 1. Soil test model

`soil_tests`: UUID PK; `farm_id` FK → `farms.id` CASCADE + index (ONLY
ownership link — farmer resolves via the farm, never from the client);
`test_date` DATE; `laboratory_name` (128), `report_number` (64),
`soil_type` (32), all nullable; nutrients as NUMERIC (never float):
pH (4,2), EC (6,3), organic carbon (5,2), N/P/K/S/Zn/Fe/Mn/Cu/B (8,2);
`notes` TEXT; `report_reference` (opaque storage ref, never a path);
`is_active` soft delete; timestamps. Many tests per farm (chronological
history); unrelated to the Step 4 one-per-farm `soil_records` summary.

## 2. Nutrient units (binding contract)

Stored EXACTLY as reported — never converted, never assumed:
pH unitless 0–14; EC dS/m 0–20; organic carbon % 0–100; N/P/K kg/ha
0–2000; S kg/ha 0–500; Zn/Fe/Mn/Cu/B mg/kg (ppm) 0–1000. Upper bounds in
Pydantic; DB CHECKs backstop non-negativity + pH range. Every form and
screen shows the unit next to the value. NULL = "not measured", never 0.

## 3. Soil history

`GET /farms/{id}/soil-tests` returns newest-first; farm details shows the
🧪 Soil Health card (latest test: pH/EC/OC/NPK + date/lab/report no, or
the empty message + `[ + माती परीक्षण नोंदवा ]`). History page lists every
record; each opens its detail screen.

## 4. Report uploads

Optional PDF/JPG/PNG via multipart (`/{id}/report`), validated by sniffing
ACTUAL bytes (`%PDF-` magic; Pillow open+verify for images — filename
never trusted), size-capped (`SOIL_REPORT_MAX_MB=10`). Stored through the
Step 10 `LocalImageStorage` CLASS with a separate root
(`storage/soil_reports`, gitignored) — same opaque-reference contract, no
new abstraction. Responses carry `has_report` only; bytes served solely
through the authed `/{id}/report` route (no public URLs). Re-upload
replaces (old file removed); delete removes the file best-effort while
the row soft-deletes.

## 5. Fertilizer application model

`fertilizer_applications`: UUID PK; `farm_crop_id` FK → `farm_crops.id`
CASCADE + index (ONLY ownership link — farmer via crop→farm); DATE;
`fertilizer_name` (128, required); `fertilizer_type` CHECK
(organic/nitrogen/phosphorus/potassium/micronutrient/npk/other, nullable);
`quantity` NUMERIC(10,3) > 0 CHECK; `quantity_unit` CHECK
(kg/quintal/litre/gram/other) stored verbatim, never converted;
`application_method` (64), `purpose` (256), `notes`; `is_active` soft
delete. A record means "farmer used X" — never a recommendation, never a
product catalog entry.

## 6. Crop integration (activity reuse, no duplication)

Creating a fertilizer record ALSO creates a Step 6 activity (type
`fertilizer_application`, status completed, same date/quantity) through
`activities_service.create_activity` — unless `record_activity: false`.
Timeline logic stays in Step 6; fertilizer detail stays here. Crop
details shows the 🧪 Fertilizer History card (recent 3 + history/add
links); history page lists newest-first; details/edit screens per record.

## 7. Authorization

Bearer auth everywhere; farmer derived server-side; farm/crop from path
only. Soil queries scope (owned live farm); fertilizer queries JOIN
through live crop on live owned farm. Missing/foreign/deleted legs share
uniform 404s (`FARM_NOT_FOUND` / `CROP_NOT_FOUND` / `SOIL_TEST_NOT_FOUND`
/ `FERTILIZER_NOT_FOUND`) — no IDOR oracle. Report bytes owner-checked.

## 8. Soft deletion

Both tables: `is_active=false` on DELETE; lists/details exclude inactive;
rows retained for future expense linkage. Report files removed
best-effort; references die with the row.

## 9. Safety limitations (binding)

No automatic dosage, no crop-specific prescriptions, no mixing
instructions, no dangerous combinations, no "apply X kg now". Forms and
screens record; nothing computes advice. Recommendation logic (if ever)
requires verified sources + explicit safety rules as a separate step.

## 10. Future recommendation architecture (untouched)

A future engine would read `soil_tests` + `fertilizer_applications` +
crop/activity context, constrained by verified agronomy rules and the
Step 9 safety policy — this step only guarantees the data it needs
exists, timestamped and farmer-scoped.
