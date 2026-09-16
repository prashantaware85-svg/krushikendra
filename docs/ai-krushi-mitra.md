# Krushi Seva — AI Krushi Mitra (Step 9)

> Scope: conversational assistant over the Step 9 RAG foundation, in
> Marathi/Hindi/English. NO diagnosis, dosages, predictions, or autonomous
> decisions — see the safety policy below and `docs/rag.md` for retrieval.

## 1. AI provider abstraction

`app/modules/ai/providers.py`: `AIProvider.generate_response(prompt,
language)` and `EmbeddingProvider.generate_embedding(text)` — service code
depends ONLY on these ABCs. Implementations: `MockChatProvider` /
`MockEmbeddingProvider` (deterministic, `[MOCK — development only]`
labelled) and `Disabled*` (fail closed). A live provider = new subclass +
factory entry + `AI_PROVIDER` name; no service/router changes. Factories
`get_chat_provider()` / `get_embedding_provider()` are the mockable seams.

## 2. Embedding provider

Isolated from retrieval (`retrieval.py` takes plain `list[float]`).
Mock embeddings are deterministic word-hash unit vectors (similar texts →
high cosine), so ranking tests exercise real math with no paid API. If the
provider fails: 503, user turn kept, NOTHING fabricated, no partial vectors
stored (ingest rolls back).

## 3. RAG architecture

```
Question → embed → similar_chunks() → top-k verified excerpts
  → build_rag_prompt() → generate_response() → answer + sources
```

Retrieval (`retrieval.py`): SQL filters (verified + active + embedded) →
PG orders candidates by pgvector `<=>`, SQLite scans the same filters →
pure-Python cosine → `RAG_MIN_SIMILARITY` gate → `RAG_TOP_K`, bounded by
`RAG_CANDIDATE_LIMIT`. See `docs/rag.md` for chunking/embeddings/search.

## 4. Document lifecycle & verification policy

`ingestion.register_document()` (unverified by default) → `ingest_text()`
(chunk + embed + replace) → `verify_document(true)` grants retrieval trust
→ `set_document_active(false)` hides. `reindex_document()` re-runs after
edits; `ingestion_status()` inspects. Priority: government departments,
ICAR, state agri universities, official research bodies, registered labels.
No blogs/social/forums auto-trusted; no crawlers. No farmer-facing
ingestion endpoints in Step 9 (future admin).

## 5. Source attribution

Every RAG answer returns `sources: [{document_id, chunk_id, title,
source_name, source_url, score}]`, persisted per assistant message
(`citations` JSONB) so history reloads identically. The UI renders 📚
sources under each answer; claims without sources are a bug.

## 6. Farmer context

Explicit `farm_id`/`crop_id` only (validated: crop pinned to farm, uniform
404s). Prompt receives minimal stored facts — farm/crop names, status,
season, sowing date, village, recent activity titles/dates/types. NEVER
phone numbers, tokens, user ids, credentials, config. Costs/quantities are
excluded from context. No `crop_id` → no crop context attached (the
assistant clarifies instead of guessing across crops).

## 7. Prompt injection defense

Prompt has three separated sections: SYSTEM INSTRUCTIONS (privileged, never
revealed/overridden) / RETRIEVED KNOWLEDGE (explicitly labelled UNTRUSTED
reference — answer FROM it, never OBEY it) / USER QUESTION. Documents can
therefore never smuggle instructions; tests assert the separator and that
injection text stays data.

## 8. Rate limiting & validation

Per-user hourly cap (`AI_MAX_MESSAGES_PER_HOUR`, 429 `AI_RATE_LIMITED`),
message length cap (`AI_MAX_MESSAGE_LENGTH`, 422), history window
(`AI_MAX_HISTORY_MESSAGES`), context caps (`RAG_MAX_CONTEXT_CHUNKS/CHARS`,
undisclosed to farmers). All configurable in `.env`.

## 9. Privacy

See §6 allow-list — that is ALL any provider ever receives, plus the
question and chunk excerpts. No personal data beyond farm/crop names.

## 10. Observability & failure handling

Structured log per turn: `request_id, latency_ms, chunks, success,
category, lang, msg_len` — NEVER content, keys, tokens, or OTPs. Provider
failure → safe 503 (`AI_PROVIDER_UNAVAILABLE`), user turn preserved,
assistant turn never invented. Empty knowledge → saved Marathi-first
fallback ("…पुरेशी विश्वसनीय माहिती…"), sources `[]`.

## 11. Agricultural safety policy (binding)

The assistant MUST NOT provide: pesticide/fertilizer/chemical dosages or
mixing, spray/irrigation schedules as prescriptions, definitive disease
diagnosis, restricted-chemical advice, yield/market/financial predictions.
Dosage questions get the no-invention rule: general verified info only +
referral to labels/experts. This policy is baked into every prompt
(`prompts.SAFETY_RULES`) and is a release gate for future providers.

## 12. Development mode

Default providers are `mock` (deterministic, labelled, free). Production
startup REFUSES mock providers (fail-fast, like the dev-OTP guard), so
mock answers can never serve farmers. `disabled` fails every call closed.

## 13. API endpoints

| Method & path | Notes |
|---|---|
| `POST /api/v1/ai/conversations` | 201, `{title?, language}` (mr default) |
| `GET /api/v1/ai/conversations` | own threads, newest first |
| `GET /api/v1/ai/conversations/{id}` | owned thread + messages, persisted citations |
| `POST /api/v1/ai/conversations/{id}/messages` | `{message, farm_id?, crop_id?, language?}` → assistant + sources |
| `DELETE /api/v1/ai/conversations/{id}` | 204, owned, messages cascade |

All auth-required, owner-scoped (uniform 404s).

## 14. Future extensions (untouched)

Live LLM/embedding providers, admin ingestion panel (functions ready),
voice input (UI placeholder exists), weather/market-aware answers (rows
already exist — composition only), image diagnosis (separate module).
