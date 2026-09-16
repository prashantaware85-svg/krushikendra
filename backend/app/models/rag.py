"""RAG knowledge-base models (Step 9).

Lifecycle: registered (``is_verified=False``, invisible to retrieval) →
indexed (chunks + embeddings stored) → verified (retrieval-eligible) →
active/inactive toggle. Only verified + active + embedded chunks are ever
retrieved (see ``app/modules/ai/retrieval.py``).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.vector import EmbeddingVector


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A curated knowledge document (trusted sources only, no crawlers)."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="mr")
    source_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One embedded excerpt of a document. Python type is list[float]."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # NOTE: dimensions MUST match AI_EMBEDDING_DIM (default 1536); changing it
    # needs a migration (ALTER COLUMN … USING) on PostgreSQL.
    embedding: Mapped[list[float] | None] = mapped_column(
        EmbeddingVector(dimensions=1536), nullable=True
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="mr")

    document: Mapped[Document] = relationship("Document", back_populates="chunks")
