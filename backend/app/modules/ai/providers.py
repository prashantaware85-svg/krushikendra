"""AI + embedding provider abstraction (mock-first).

Service code depends ONLY on the ABCs below. A live provider = new subclass
+ factory entry + provider name; no service/router changes. Factories
``get_chat_provider()`` / ``get_embedding_provider()`` are the mockable seams.

- Mock embeddings are deterministic word-hash unit vectors (similar texts →
  high cosine), so ranking tests exercise real math with no paid API.
- ``disabled`` fails every call closed (fail-closed, never fabricated).
- Production startup REFUSES mock providers (fail-fast in config).
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

from app.core.config import get_settings


class ProviderError(Exception):
    """Provider failure — carries no secrets or payloads."""


class ChatProvider(ABC):
    """Text-generation seam."""

    @abstractmethod
    def generate_response(self, prompt: str, language: str) -> str:
        """Return the assistant answer for a fully-built RAG prompt."""
        raise NotImplementedError


class EmbeddingProvider(ABC):
    """Text→vector seam (isolated from retrieval math)."""

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """Return a unit-length vector of ``AI_EMBEDDING_DIM`` floats."""
        raise NotImplementedError


class MockChatProvider(ChatProvider):
    """Deterministic dev/test chat: grounds every claim in prompt excerpts.

    The prompt built by ``prompts.build_rag_prompt`` carries a machine-readable
    ``EXCERPT`` block (``[S1] Title: …`` lines + quoted content). The mock
    answers ONLY from those lines — with zero excerpts it refuses instead of
    inventing (the service uses the graceful fallback in that case).
    """

    MOCK_LABEL = "[MOCK — development only]"

    def generate_response(self, prompt: str, language: str) -> str:
        titles: list[str] = []
        first_body = ""
        in_excerpts = False
        for line in prompt.splitlines():
            if line.strip() == "=== EXCERPTS ===":
                in_excerpts = True
                continue
            if line.strip() == "=== END EXCERPTS ===":
                break
            if not in_excerpts:
                continue
            if line.startswith("[S"):
                title = line.split("Title:", 1)[1].strip() if "Title:" in line else line
                titles.append(title)
            elif line.strip().startswith("> ") and not first_body:
                first_body = line.strip()[2:].strip()
        if not titles:
            raise ProviderError("Mock provider received no excerpts.")
        cited = ", ".join(f"[{i + 1}] {t}" for i, t in enumerate(titles))
        snippet = f" {first_body[:200]}" if first_body else ""
        return (
            f"{self.MOCK_LABEL} Based on {len(titles)} verified excerpt(s) "
            f"({cited}):{snippet}"
        )


class DisabledChatProvider(ChatProvider):
    """Fail-closed chat (no network, no fabrication)."""

    def generate_response(self, prompt: str, language: str) -> str:
        raise ProviderError("AI provider is disabled.")


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic word-hash unit vectors (documented mock).

    Each word hashes to ``HASH_FANOUT`` buckets; counts accumulate, then the
    vector is L2-normalised — so lexically similar texts get high cosine.
    """

    HASH_FANOUT = 4

    def generate_embedding(self, text: str) -> list[float]:
        dim = get_settings().ai_embedding_dim
        vec = [0.0] * dim
        words = (text or "").lower().split()
        if not words:
            return vec
        for word in words:
            for i in range(self.HASH_FANOUT):
                digest = hashlib.sha256(f"{word}#{i}".encode("utf-8")).digest()
                vec[int.from_bytes(digest[:4], "big") % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]


class DisabledEmbeddingProvider(EmbeddingProvider):
    """Fail-closed embeddings."""

    def generate_embedding(self, text: str) -> list[float]:
        raise ProviderError("Embedding provider is disabled.")


def get_chat_provider(name: str | None = None) -> ChatProvider:
    """Factory seam (mock by default; ``disabled`` fails closed)."""
    provider = (name or get_settings().ai_provider).lower()
    if provider == "mock":
        return MockChatProvider()
    if provider == "disabled":
        return DisabledChatProvider()
    raise ProviderError(f"Unknown AI provider: {provider}")


def get_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    """Factory seam (mock by default; ``disabled`` fails closed)."""
    provider = (name or get_settings().ai_embedding_provider).lower()
    if provider == "mock":
        return MockEmbeddingProvider()
    if provider == "disabled":
        return DisabledEmbeddingProvider()
    raise ProviderError(f"Unknown embedding provider: {provider}")
