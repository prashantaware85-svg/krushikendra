"""AI request/response contracts (Pydantic v2, no secrets leak)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    language: Literal["mr", "hi", "en"] = "mr"


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    language: str


class SourceOut(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source_name: str
    source_url: str | None = None
    score: float


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceOut] = Field(default_factory=list)


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    farm_id: uuid.UUID | None = None
    crop_id: uuid.UUID | None = None
    language: Literal["mr", "hi", "en"] | None = None


class ChatReplyOut(BaseModel):
    conversation_id: uuid.UUID
    message: MessageOut
    sources: list[SourceOut] = Field(default_factory=list)
