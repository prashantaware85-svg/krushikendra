"""Document ingestion (service-level; no farmer-facing endpoints in this step).

``register_document()`` (unverified by default) → ``ingest_text()``
(chunk + embed + replace) → ``verify_document(True)`` grants retrieval
trust. Provider failure rolls ingest back: NOTHING fabricated, no partial
vectors stored.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.rag import Document, DocumentChunk
from app.modules.ai.chunking import chunk_text
from app.modules.ai.providers import ProviderError, get_embedding_provider


def register_document(
    db: Session,
    *,
    title: str,
    language: str = "mr",
    source_name: str | None = None,
    source_url: str | None = None,
    doc_type: str | None = None,
) -> Document:
    """Register a document (unverified → invisible to retrieval)."""
    document = Document(
        title=title,
        language=language,
        source_name=source_name,
        source_url=source_url,
        doc_type=doc_type,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def _get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise AppError(
            "Document not found.",
            code="DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return document


def ingest_text(db: Session, document_id: uuid.UUID, text: str) -> Document:
    """Chunk + embed + REPLACE all chunks (no orphans). Rolls back on failure."""
    document = _get_document(db, document_id)
    pieces = chunk_text(text)
    provider = get_embedding_provider()
    try:
        vectors = [provider.generate_embedding(piece) for piece in pieces]
    except ProviderError as exc:
        db.rollback()
        raise AppError(
            "Embedding service is currently unavailable. Nothing was stored.",
            code="EMBEDDING_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    for index, (piece, vector) in enumerate(zip(pieces, vectors)):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=piece,
                embedding=vector,
                language=document.language,
            )
        )
    document.content_hash = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    db.commit()
    db.refresh(document)
    return document


def verify_document(db: Session, document_id: uuid.UUID, verified: bool = True) -> Document:
    """Grant/revoke retrieval trust (curated sources only)."""
    document = _get_document(db, document_id)
    document.is_verified = verified
    db.commit()
    db.refresh(document)
    return document


def set_document_active(db: Session, document_id: uuid.UUID, active: bool) -> Document:
    """Hide/reveal a document without deleting history."""
    document = _get_document(db, document_id)
    document.is_active = active
    db.commit()
    db.refresh(document)
    return document


def reindex_document(db: Session, document_id: uuid.UUID, text: str) -> Document:
    """Re-run chunk + embed after edits (same replace path as ingest)."""
    return ingest_text(db, document_id, text)


def ingestion_status(db: Session, document_id: uuid.UUID) -> dict:
    """Inspect counts/flags for the future admin panel."""
    document = _get_document(db, document_id)
    total = (
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count()
    )
    embedded = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document.id,
            DocumentChunk.embedding.is_not(None),
        )
        .count()
    )
    return {
        "document_id": str(document.id),
        "title": document.title,
        "is_verified": document.is_verified,
        "is_active": document.is_active,
        "total_chunks": total,
        "embedded_chunks": embedded,
        "content_hash": document.content_hash,
    }
