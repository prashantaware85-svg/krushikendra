# Krushi Seva — Crop Image Analysis Foundation (Step 10)

> Scope: photo upload → validation → vision observation (uncertain
> language) → RAG supporting info → safe next steps. NO diagnosis, NO
> dosages, NO prescriptions, NO autonomous decisions — ever in this step.

## 1. Image analysis architecture

```
Farmer → Farm → Crop (ownership pinned, both live)
  → 1–3 photos → Pillow validation (magic bytes, not extension)
  → quality gate (size/darkness/blur heuristics + capture guidance)
  → sha256 → LocalImageStorage (opaque refs, gitignored dir)
  → crop_image_analyses row (uploaded → processing → completed/failed)
  → VisionProvider.analyze_crop_image() → uncertain result
  → RAG supporting-info lookup (verified docs only)
  → safe response contract (condition?/confidence/observations/quality/
    disclaimer/sources/next-steps)
```

Sync flow in Step 10 (a worker queue is the documented future path).

## 2. Vision provider abstraction

`VisionProvider.analyze_crop_image(images, language, crop_name)` returns a
normalized `VisionResult` (possible_condition | None, confidence 0–1 |
None, observations[], quality, needs_info[], next_steps[]). `MockVision`
(deterministic leaf-spot-like finding, `is_mock=True`) and `Disabled`
(fail closed) ship now; a live provider = subclass + factory + name.
`ProviderError` carries no secrets/payloads. Config: VISION_PROVIDER
(default mock; production refuses mock at startup), VISION_API_KEY (never
in code/logs/frontend), VISION_MODEL/BASE_URL/TIMEOUT_SECONDS.

## 3. Upload validation

JPG/PNG/WEBP only (Pillow `verify()` on actual bytes); 1–3 files
(`VISION_MAX_IMAGES`); size cap (`VISION_MAX_FILE_MB=8`); dimension caps
(`VISION_MIN/MAX_DIMENSION` 200/4096px). Quality heuristics: too-small,
too-dark (mean luminance), blurry (interior Laplacian variance — borders
excluded, since kernel edge responses mask flat interiors). Failures
return IMAGE_QUALITY_INSUFFICIENT (+ how to retake) instead of any finding.

## 4. Storage abstraction

`ImageStorage` (upload/get_reference/delete) → `LocalImageStorage`
(UUID filenames under `backend/storage/`). Swap for S3-compatible later
without touching service/router. Frontend never sees paths — an authed
byte-serving route (`/{id}/image`, owner-scoped) replaces public URLs.

## 5. Database model

`crop_image_analyses`: UUID PK; `farm_crop_id` FK CASCADE + index (ONLY
ownership link — farmer via crop→farm→profile); `image_reference` +
`extra_image_references` JSON (images 2–3); `image_hash` (sha256, index);
status CHECK (uploaded/processing/completed/failed) + indexes on
status/created_at; provider/model; `possible_condition`, `confidence`
(NUMERIC 0–1 CHECK), `observations` Text, `needs_info`/`next_steps` JSON,
`image_quality` CHECK + `quality_notes`; `sources` JSON (RAG citations);
`response_language` (default mr); `is_active` soft delete.

## 6. API endpoints

| Method & path | Notes |
|---|---|
| `POST /crop-images` (multipart: farm_id, crop_id, language?, images[]) | 201 completed (sync); 422 IMAGE_*; 429 hourly cap; 503 marks failed |
| `GET /crop-images` | own history, newest, bounded |
| `GET /crop-images/{id}` | owned result contract (no refs/paths/secrets) |
| `GET /crop-images/{id}/image` | owned bytes, correct media type |
| `POST /crop-images/{id}/analyze` | idempotent re-run |
| `DELETE /crop-images/{id}` | 204, row soft-deleted + files removed |

Ownership resolves analysis → live crop → live farm → farmer (uniform
404s, manipulated pairs rejected). Rate limits: hourly cap
(`VISION_MAX_ANALYSES_PER_HOUR=10`), count/size/dimension caps.

## 7. RAG integration

After vision, condition + observations are embedded and matched against
VERIFIED documents only (`similar_chunks`, same trust gate as Step 9).
Sources attach as "general supporting information" with titles — they can
NEVER upgrade uncertainty: no dosage/prescription text is generated from
them, and empty knowledge yields sources `[]` (analysis still completes).

## 8. Safety limitations (binding)

Possible-condition language only ("Leaf spot-like symptoms", never
"definitely X"); confidence shown as %; every response carries the
not-a-diagnosis disclaimer (mr/hi/en); mock results carry `[MOCK]` +
`is_mock`. Forbidden everywhere: dosages, mixing, combinations,
prescriptions, fertilizer rates, spray schedules, definitive diagnosis,
autonomous actions. Dosage-type questions → expert/label referral.

## 9. Image privacy

Auth + ownership on every byte; opaque references; no public URLs; files
removed on delete (best-effort) with rows soft-deleted; images sent to a
provider ONLY on explicit analyze actions; logs carry IDs/timings only —
never bytes, keys, or content. Retention assumption: files live until the
farmer deletes the analysis (documented; formal retention policy is future).

## 10. Rate limits & failure handling

Hourly per-user cap, 1–3 images, 8 MB / 4096px / 200px-min caps, provider
timeout, all configurable. Provider failure → row `failed` + safe 503
(`VISION_PROVIDER_UNAVAILABLE`); user-facing copy says photos are saved
and retry is possible; nothing fabricated, internals never exposed.

## 11. Future improvements (untouched)

Worker queue for analysis; S3-compatible storage; live vision provider;
multi-image joint reasoning; admin review queue; analysis-linked Krushi
Mitra context (today: link to `/ai` with farm/crop selectors); formal
retention policy; on-device quality pre-check.
