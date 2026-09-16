"""AI Krushi Mitra endpoints (thin: auth + validation → service)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.ai import schemas, service
from app.modules.common.dependencies import get_current_farmer_id

router = APIRouter(prefix="/ai/conversations", tags=["ai"])


@router.post("", response_model=schemas.ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: schemas.ConversationCreate,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Start a thread (201, ``{title?, language}``, mr default)."""
    return service.create_conversation(
        db, farmer_id=farmer_id, title=payload.title, language=payload.language
    )


@router.get("", response_model=list[schemas.ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> list[dict]:
    """Own threads, newest first."""
    return service.list_conversations(db, farmer_id=farmer_id)


@router.get("/{conversation_id}", response_model=schemas.ConversationDetailOut)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """Owned thread + messages (persisted citations reload identically)."""
    return service.get_conversation_detail(
        db, farmer_id=farmer_id, conversation_id=conversation_id
    )


@router.post("/{conversation_id}/messages", response_model=schemas.ChatReplyOut)
def post_message(
    conversation_id: uuid.UUID,
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> dict:
    """RAG answer + sources (mock-first, never fabricated)."""
    return service.send_message(
        db,
        farmer_id=farmer_id,
        conversation_id=conversation_id,
        message=payload.message,
        language=payload.language,
        farm_id=payload.farm_id,
        crop_id=payload.crop_id,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    farmer_id: uuid.UUID = Depends(get_current_farmer_id),
) -> Response:
    """Delete an owned thread (204, messages cascade)."""
    service.delete_conversation(
        db, farmer_id=farmer_id, conversation_id=conversation_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
