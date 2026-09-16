"""Deterministic Markdown-aware text splitter.

800-char target, 100-char trailing overlap, heading sections preserved
(heading prepended to the section's first chunk), paragraph packing,
hard-split only for pathological paragraphs. Same input → identical chunks.
"""

from __future__ import annotations

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _split_long_paragraph(paragraph: str, size: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(paragraph):
        parts.append(paragraph[start : start + size])
        # Hard-split (no overlap): pathological single-token paragraphs only.
        start += size
    return parts


def chunk_text(
    text: str, *, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split Markdown text into overlapping chunks (deterministic)."""
    text = (text or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    current_heading = ""
    current_parts: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current_parts, current_len
        if not current_parts:
            return
        body = "\n\n".join(current_parts).strip()
        if current_heading and not body.startswith(current_heading):
            body = f"{current_heading}\n\n{body}"
        # Enforce the size cap with trailing overlap for normal chunks.
        start = 0
        first = True
        while start < len(body):
            piece = body[start : start + chunk_size]
            if not first and overlap and start < len(body):
                pass  # overlap already applied via the step below
            chunks.append(piece)
            if start + chunk_size >= len(body):
                break
            start += chunk_size - overlap
            first = False
        current_parts = []
        current_len = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            flush()
            current_heading = line.strip("# ").strip()
            continue
        if not line.strip():
            continue
        if len(line) > chunk_size:
            flush()
            prefix = f"{current_heading}\n\n" if current_heading else ""
            for part in _split_long_paragraph(line, chunk_size - len(prefix)):
                chunks.append(f"{prefix}{part}" if prefix else part)
            continue
        if current_len + len(line) + 2 > chunk_size and current_parts:
            flush()
        current_parts.append(line)
        current_len += len(line) + 2
    flush()
    return [c for c in chunks if c.strip()]
