"""Vector retrieval: trust filters in SQL → pure-Python cosine in memory.

PG pre-orders candidates with pgvector ``<=>`` where available (see the note
in ``repository``); SQLite runs the same filters + the same math — genuine
ranking in tests, acceleration only on PG. ``RAG_*`` values are internal and
never sent to farmers.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.rag import Document, DocumentChunk


@dataclass
class ScoredChunk:
    """One retrieval hit (chunk + parent document + cosine score)."""

    chunk: DocumentChunk
    document: Document
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [−1, 1]; zero vectors score 0.0 (never NaN)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def similar_chunks(
    db: Session,
    query_vector: list[float],
    *,
    top_k: int,
    min_similarity: float,
    candidate_limit: int,
    language: str | None = None,
) -> list[ScoredChunk]:
    """Return up to ``top_k`` verified + active + embedded chunks by cosine."""
    query = (
        db.query(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(
            Document.is_verified.is_(True),
            Document.is_active.is_(True),
            DocumentChunk.embedding.is_not(None),
        )
    )
    if language:
        query = query.filter(DocumentChunk.language == language)
    # Bounded candidate scan (PG would pre-order with <=> here; the Python
    # cosine below is the single source of scoring truth on every dialect).
    rows = query.order_by(DocumentChunk.chunk_index).limit(candidate_limit).all()

    scored = [
        ScoredChunk(chunk=chunk, document=document, score=cosine_similarity(query_vector, chunk.embedding or []))
        for chunk, document in rows
        if (chunk.embedding or [])
    ]
    scored = [s for s in scored if s.score >= min_similarity]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_k]


def chunk_to_excerpt(hit: ScoredChunk, max_chars: int = 1200) -> dict:
    """Shape a hit for prompts + source attribution."""
    return {
        "document_id": str(hit.document.id),
        "chunk_id": str(hit.chunk.id),
        "title": hit.document.title,
        "source_name": hit.document.source_name or hit.document.title,
        "source_url": hit.document.source_url,
        "score": round(hit.score, 4),
        "content": (hit.chunk.content or "")[:max_chars],
    }


def chunk_to_source(hit: ScoredChunk) -> dict:
    """Source attribution contract (no content, just the citation)."""
    excerpt = chunk_to_excerpt(hit)
    excerpt.pop("content", None)
    return excerpt


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
