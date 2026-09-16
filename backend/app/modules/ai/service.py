"""AI chat policy: RAG answer + sources, mock-first, never fabricated.

Flow: embed question → ``similar_chunks()`` → top-k verified excerpts →
``build_rag_prompt()`` → ``generate_response()`` → answer + sources.
Empty knowledge → saved Marathi-first fallback, sources ``[]``. Provider
failure → safe 503, user turn preserved, assistant turn never invented.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.ai import repository
from app.modules.ai.prompts import build_rag_prompt, fallback_for
from app.modules.ai.providers import ProviderError, get_chat_provider, get_embedding_provider
from app.modules.ai.retrieval import chunk_to_excerpt, chunk_to_source, similar_chunks

logger = logging.getLogger("krushi-seva.ai")


def _not_found() -> AppError:
    return AppError(
        "Conversation not found.",
        code="CONVERSATION_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def create_conversation(
    db: Session, *, farmer_id: uuid.UUID, title: str | None, language: str
) -> dict:
    conversation = repository.create_conversation(
        db, farmer_id=farmer_id, title=title, language=language
    )
    return {"id": conversation.id, "title": conversation.title, "language": conversation.language}


def list_conversations(db: Session, *, farmer_id: uuid.UUID) -> list[dict]:
    return [
        {"id": c.id, "title": c.title, "language": c.language}
        for c in repository.list_conversations(db, farmer_id=farmer_id)
    ]


def get_conversation_detail(
    db: Session, *, farmer_id: uuid.UUID, conversation_id: uuid.UUID
) -> dict:
    conversation = repository.get_owned_conversation(
        db, farmer_id=farmer_id, conversation_id=conversation_id
    )
    if conversation is None:
        raise _not_found()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "language": conversation.language,
        "messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "sources": repository.parse_sources(m),
            }
            for m in repository.list_messages(db, conversation_id=conversation.id)
        ],
    }


def delete_conversation(
    db: Session, *, farmer_id: uuid.UUID, conversation_id: uuid.UUID
) -> None:
    conversation = repository.get_owned_conversation(
        db, farmer_id=farmer_id, conversation_id=conversation_id
    )
    if conversation is None:
        raise _not_found()
    repository.delete_conversation(db, conversation)


def send_message(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message: str,
    language: str | None = None,
    farm_id: uuid.UUID | None = None,
    crop_id: uuid.UUID | None = None,
) -> dict:
    """One RAG turn. Returns ``{conversation_id, message, sources}``."""
    settings = get_settings()
    started = time.perf_counter()
    conversation = repository.get_owned_conversation(
        db, farmer_id=farmer_id, conversation_id=conversation_id
    )
    if conversation is None:
        raise _not_found()

    text = (message or "").strip()
    if not text:
        raise AppError(
            "Message must not be empty.",
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if len(text) > settings.ai_max_message_length:
        raise AppError(
            f"Message is too long (max {settings.ai_max_message_length} characters).",
            code="AI_MESSAGE_TOO_LONG",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    recent = repository.count_recent_user_messages(
        db, farmer_id=farmer_id, window=timedelta(hours=1)
    )
    if recent >= settings.ai_max_messages_per_hour:
        raise AppError(
            "Hourly message limit reached. Please try again later.",
            code="AI_RATE_LIMITED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    lang = language or conversation.language or "mr"
    # User turn is persisted FIRST so provider failures never lose it.
    repository.add_message(
        db, conversation_id=conversation.id, role="user", content=text
    )

    try:
        query_vector = get_embedding_provider().generate_embedding(text)
    except ProviderError as exc:
        raise AppError(
            "Assistant is currently unavailable. Your message was saved.",
            code="AI_PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    hits = similar_chunks(
        db,
        query_vector,
        top_k=settings.rag_top_k,
        min_similarity=settings.rag_min_similarity,
        candidate_limit=settings.rag_candidate_limit,
    )
    # Context caps (undisclosed to farmers): bound chunks AND characters.
    excerpts = [chunk_to_excerpt(h) for h in hits[: settings.rag_max_context_chunks]]
    total_chars = 0
    bounded: list[dict] = []
    for excerpt in excerpts:
        total_chars += len(excerpt["content"])
        if total_chars > settings.rag_max_context_chars:
            break
        bounded.append(excerpt)

    if not bounded:
        # Graceful insufficient-context fallback (saved, sources []).
        content = fallback_for(lang)
        assistant = repository.add_message(
            db, conversation_id=conversation.id, role="assistant", content=content, sources=[]
        )
        logger.info(
            "ai_turn chunks=0 success=true lang=%s msg_len=%d latency_ms=%d",
            lang, len(text), int((time.perf_counter() - started) * 1000),
        )
        return {
            "conversation_id": conversation.id,
            "message": {
                "id": assistant.id,
                "conversation_id": conversation.id,
                "role": "assistant",
                "content": content,
                "sources": [],
            },
            "sources": [],
        }

    context_bits = []
    if farm_id:
        context_bits.append(f"farm_id={farm_id}")
    if crop_id:
        context_bits.append(f"crop_id={crop_id}")
    prompt = build_rag_prompt(text, bounded, farmer_context="; ".join(context_bits))
    try:
        answer = get_chat_provider().generate_response(prompt, lang)
    except ProviderError as exc:
        raise AppError(
            "Assistant is currently unavailable. Your message was saved.",
            code="AI_PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    sources = [chunk_to_source(h) for h in hits[: len(bounded)]]
    assistant = repository.add_message(
        db,
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        sources=sources,
    )
    logger.info(
        "ai_turn chunks=%d success=true lang=%s msg_len=%d latency_ms=%d",
        len(sources), lang, len(text), int((time.perf_counter() - started) * 1000),
    )
    return {
        "conversation_id": conversation.id,
        "message": {
            "id": assistant.id,
            "conversation_id": conversation.id,
            "role": "assistant",
            "content": answer,
            "sources": sources,
        },
        "sources": sources,
    }
