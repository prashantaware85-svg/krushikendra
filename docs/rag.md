# Krushi Seva — RAG Knowledge Base (Step 9)

> Document → Chunk → Embedding → pgvector → Similarity → Chunks → LLM →
> Answer + Sources. Curated trusted sources only; no crawlers.

## 1. Architecture

```
register_document() → ingest_text() → chunk_text() → embed → document_chunks
                                                        ↓ (verified + active)
ask(): embed(question) → similar_chunks() → build_rag_prompt() → chat
```

## 2. Document lifecycle

States: registered (`is_verified=false`, invisible to retrieval) →
indexed (chunks + embeddings stored) → verified (retrieval-eligible) →
active/inactive toggle. `content_hash` (sha256) detects drift.
`reindex_document()` re-runs chunk+embed after edits (replaces chunks —
no orphans). `ingestion_status()` exposes counts/flags for the future
admin panel. Verification policy: government, ICAR, state agri
universities, official research, registered labels. Nothing else is
trusted by default.

## 3. Chunking

Deterministic Markdown-aware splitter (`chunking.py`): 800-char target,
100-char trailing overlap, heading sections preserved (heading in metadata
AND prepended to the section's first chunk), paragraph packing, hard-split
only for pathological paragraphs. Metadata per chunk: heading,
chunk_index, total_chunks, content_hash. Same input → identical chunks
(tested). `token_count` is a rough chars/4 estimate (documented, for
future budget math — not billing). PDF later = extractor → Markdown →
same `chunk_document` path.

## 4. Embeddings

Dimension from `AI_EMBEDDING_DIM` (default 1536) — MUST match the
`VECTOR(1536)` column in migration 0008; changing it needs a new migration
(ALTER COLUMN … USING). Provider isolated behind `EmbeddingProvider`;
failures roll ingest back (no partial/fake vectors). Mock = deterministic
word-hash unit vectors (documented in providers.py).

## 5. Vector search

`retrieval.similar_chunks()`: trust filters in SQL on every dialect →
PG pre-orders candidates with pgvector `<=>` (needs the `vector`
extension — migration creates it, loudly failing if absent) → pure-Python
cosine scoring → `RAG_MIN_SIMILARITY` (default 0.15) → `RAG_TOP_K`
(default 4), candidates bounded by `RAG_CANDIDATE_LIMIT` (default 500).
SQLite runs the same filters + same math (no extension needed) — genuine
ranking in tests, acceleration only on PG. Retrieval values are internal
(`RAG_*` never sent to farmers).

## 6. Source attribution & history

Citations persisted per assistant message (`citations` JSONB) — history
shows the same sources forever. Response contract:
`{message, sources: [{document_id, chunk_id, title, source_name,
source_url, score}]}`.

## 7. Storage notes

`EmbeddingVector` TypeDecorator: `VECTOR(dim)` on PG, JSON TEXT on SQLite —
Python type is `list[float]` everywhere. `metadata` column is JSON/JSONB.
No raw provider payloads stored; no secrets in any column (user content +
citations only).
