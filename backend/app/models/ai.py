"""AI Krushi Mitra conversation models (Step 9).

Threads are farmer-owned; assistant messages persist their ``sources`` so
history reloads identically. No personal data beyond the farmer link.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AiConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One farmer chat thread."""

    __tablename__ = "ai_conversations"

    # NOTE: plain UUID (no hard FK) — the users table lives in the auth
    # domain, outside this rebuild. Ownership is enforced in the service
    # layer (every query filters on this column → uniform 404s, no oracle).
    farmer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="mr")

    messages: Mapped[list[AiMessage]] = relationship(
        "AiMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AiMessage.created_at",
    )


class AiMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One turn (``user`` / ``assistant``) in a conversation."""

    __tablename__ = "ai_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user|assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON array of {document_id, chunk_id, title, source_name, source_url,
    # score} — persisted so history shows the same sources forever.
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[AiConversation] = relationship(
        "AiConversation", back_populates="messages"
    )
