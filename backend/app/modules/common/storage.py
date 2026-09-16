"""Opaque local file storage (shared by vision / soil / health).

Contract: callers pass raw bytes + get back an opaque reference (never a
path). Each domain uses its own root (``storage/crop_images``,
``storage/soil_reports``, ``storage/health_photos``) but the SAME class —
no duplicated logic. The frontend never sees references directly; bytes are
served through authed routes only.
"""

from __future__ import annotations

import uuid
from pathlib import Path


class LocalFileStorage:
    """UUID-named files under a gitignored root directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _guarded(self, reference: str) -> Path:
        if not reference or ".." in reference or "/" in reference or "\\" in reference:
            raise ValueError("Invalid file reference.")
        return self.root / reference

    def save_bytes(self, data: bytes, suffix: str) -> str:
        """Persist bytes; return the opaque reference."""
        self.root.mkdir(parents=True, exist_ok=True)
        clean = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
        reference = f"{uuid.uuid4().hex}{clean}"
        (self.root / reference).write_bytes(data)
        return reference

    def read_bytes(self, reference: str) -> bytes | None:
        """Return bytes, or None when the file is gone."""
        try:
            return self._guarded(reference).read_bytes()
        except (OSError, ValueError):
            return None

    def delete(self, reference: str | None) -> None:
        """Best-effort removal (missing files are not an error)."""
        if not reference:
            return
        try:
            self._guarded(reference).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
