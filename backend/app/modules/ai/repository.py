"""AI persistence: conversations + messages (CRUD only, no policy)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage


def create_conversation(
    db: Session, *, farmer_id: uuid.UUID, title: str | None, language: str
) -> AiConversation:
    conversation = AiConversation(
        farmer_user_id=farmer_id, title=title, language=language
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, *, farmer_id: uuid.UUID) -> list[AiConversation]:
    return (
        db.query(AiConversation)
        .filter(AiConversation.farmer_user_id == farmer_id)
        .order_by(AiConversation.created_at.desc())
        .all()
    )


def get_owned_conversation(
    db: Session, *, farmer_id: uuid.UUID, conversation_id: uuid.UUID
) -> AiConversation | None:
    """Owner-scoped fetch (None → caller raises uniform 404, no oracle)."""
    return (
        db.query(AiConversation)
        .filter(
            AiConversation.id == conversation_id,
            AiConversation.farmer_user_id == farmer_id,
        )
        .first()
    )


def delete_conversation(db: Session, conversation: AiConversation) -> None:
    db.delete(conversation)  # messages cascade
    db.commit()


def list_messages(db: Session, *, conversation_id: uuid.UUID) -> list[AiMessage]:
    return (
        db.query(AiMessage)
        .filter(AiMessage.conversation_id == conversation_id)
        .order_by(AiMessage.created_at.asc())
        .all()
    )


def add_message(
    db: Session,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> AiMessage:
    message = AiMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources_json=json.dumps(sources or []),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def count_recent_user_messages(
    db: Session, *, farmer_id: uuid.UUID, window: timedelta
) -> int:
    """User turns in the last ``window`` (hourly rate-limit counter)."""
    since = datetime.now(timezone.utc) - window
    return (
        db.query(AiMessage)
        .join(AiConversation, AiMessage.conversation_id == AiConversation.id)
        .filter(
            AiConversation.farmer_user_id == farmer_id,
            AiMessage.role == "user",
            AiMessage.created_at >= since,
        )
        .count()
    )


def parse_sources(message: AiMessage) -> list[dict]:
    """Sources persisted per assistant message (history reloads identically)."""
    try:
        data = json.loads(message.sources_json or "[]")
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []
