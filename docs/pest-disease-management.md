# Krushi Seva — Pest & Disease Management (Step 12)

> Scope: recording and tracking field observations, catalogue reference
> labels, recorded actions, observation photos, and links to Step 10
> analyses. NO diagnosis, NO prescriptions, NO dosages, NO spray advice —
> Step 12 tracks; it never decides treatment.

## 1. Pest catalogue

`pests`: UUID PK; unique name; local/scientific names, category,
description (all nullable); `is_verified` (default false) + `is_active`.
Seed rows are created UNVERIFIED with a "SAMPLE (dev only)" marker, so
sample data can never pass as trusted catalogue data. List endpoints
return active rows with the flag exposed (information, never a diagnosis).

## 2. Disease catalogue

`diseases`: same shape and rules as pests. Matching a catalogue row (by
linking `pest_id`/`disease_id`) records "farmer picked this label" — the
system NEVER treats the match as a confirmed diagnosis. Deleting a
catalogue row SETs NULL on observations (history survives).

## 3. Health observation model

`crop_health_observations`: UUID PK; `farm_crop_id` FK CASCADE (ONLY
ownership link — farmer resolves via crop→farm→profile); `observation_type`
(pest/disease/unknown/other); optional `pest_id`/`disease_id` (SET NULL);
`observed_name` free text kept verbatim (never auto-converted); DATE;
`severity` (low/medium/high/unknown — display only, never a treatment
trigger); optional NUMERIC `affected_area` + unit (acre/hectare/guntha/
percentage — shares the farm vocabulary, display only, no conversion
math); `symptoms`/`notes` TEXT; `status`
(observed/monitoring/resolved/recurring); `source`
(farmer/image_analysis/expert/other); `photo_references` JSON (opaque Step
10 refs); `linked_image_analysis_id` FK SET NULL (pointer only, never
merged); `is_active` soft delete. Business rule: `unknown` type carries NO
catalogue links (422 otherwise, on create AND on type-changing updates).

## 4. Severity

Four display values, no semantics attached. The codebase contains no
`if severity == high → recommend` branch by design (verified by review —
severity appears only in labels, ordering, and dots).

## 5. Status

observed → monitoring → resolved (or recurring) via plain PUT updates
(Mark Monitoring / Mark Resolved buttons). No workflow engine.

## 6. Symptoms

Farmer-observed free text (leaf spots, yellowing, wilting, holes, curling,
stem/fruit damage, discoloration, stunted growth, …). Stored and shown
verbatim; never parsed into a diagnosis.

## 7. Photos

Step 10 `LocalImageStorage` CLASS reused with a dedicated root
(`storage/health_photos`, gitignored) — same opaque-reference contract, no
duplicated logic. JPG/PNG/WEBP through the Step 10 gates (magic bytes,
size/dimension caps, darkness/blur heuristics); max 3 per observation
(`VISION_MAX_IMAGES` shared cap). Responses carry `has_photos` only; bytes
served solely through the authed `/{id}/photos/{index}` route (no public
URLs). Delete removes files best-effort while the row soft-deletes.

## 8. Image analysis link

An observation may point at a Step 10 analysis, validated as live +
farmer-owned at link time (foreign/deleted analyses 404 without leaking).
Details show a small embedded summary (possible condition + confidence +
view link) under its own heading with the not-a-diagnosis caveat — the two
records stay separate objects end to end.

## 9. Health actions

`health_actions`: UUID PK; `observation_id` FK CASCADE; DATE;
`action_type` CHECK (monitoring/sanitation/pruning/removal/
irrigation_adjustment/fertilizer_adjustment/biological_control/
chemical_application/other); `description` required ("what was done");
`product_name`/`quantity`/`quantity_unit`/`notes` optional USER-ENTERED
facts (a recorded `chemical_application` with a product name is a farmer
report, never system output — no dosage is ever generated or validated as
safe); `is_active` soft delete. Nested under `/health/{observation_id}/
actions…` with ownership re-resolved per call.

## 10. Authorization

Bearer auth everywhere; farmer derived server-side; farm/crop/observation
from path only. Observation queries JOIN live crop → live owned farm;
action routes re-resolve the observation to its (farm, crop) through owned
crops only. Missing/foreign/deleted legs share uniform 404s
(`FARM_NOT_FOUND` / `CROP_NOT_FOUND` / `OBSERVATION_NOT_FOUND` /
`ACTION_NOT_FOUND`, plus `PEST_INVALID` / `DISEASE_INVALID` /
`ANALYSIS_LINK_INVALID` for bad links) — no IDOR oracle.

## 11. RAG integration

Step 12 stores NO treatment text, so there is nothing to hallucinate from.
When Krushi Mitra answers observation questions it uses the unchanged Step
9 pipeline (verified docs only, insufficient-context fallback); the
frontend passes crop + observation facts (type, observed name, symptoms,
severity, date) as explicit context — minimum necessary, no personal data.
Future treatment guidance must be a separate validated module.

## 12. Safety limitations (binding)

No severity→treatment rules; no disease→chemical mapping; no "spray
immediately"; no dosages, mixing, combinations, schedules, diagnoses, or
predictions anywhere in code, UI copy, or docs. Mock/seed data is labelled
and unverified. These prohibitions are release gates, not TODOs.

## 13. Future treatment recommendation architecture (untouched)

A separate validated module would consume observations + actions +
verified agronomy sources under explicit safety rules and expert review —
this step only guarantees the tracked data it needs exists, timestamped
and farmer-scoped.
