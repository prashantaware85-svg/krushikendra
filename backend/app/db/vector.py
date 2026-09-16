"""Portable embedding column type (Step 9).

PostgreSQL: real pgvector `VECTOR(dim)` (indexable, `<=>` searchable).
SQLite/tests: TEXT holding a JSON array (same Python type — list[float] —
on both sides, so service/retrieval code is dialect-blind).

pgvector is therefore USED for storage on PG while the suite runs without
any extension. Similarity math lives in retrieval.py (pure Python cosine),
with a pgvector-ordered candidate path on PG (see repository note there).
"""

from __future__ import annotations

import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class EmbeddingVector(TypeDecorator):
    """list[float] ⇄ VECTOR(dim) on PG, JSON TEXT on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        values = [float(v) for v in value]
        if dialect.name == "postgresql":
            return values  # pgvector serializes the list itself
        return json.dumps(values)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return [float(v) for v in json.loads(value)]
        return [float(v) for v in value]
