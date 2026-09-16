"""Soil report upload validation (sniffs ACTUAL bytes, never filenames).

PDF via ``%PDF-`` magic; JPG/PNG via Pillow open+verify. Size-capped
(``SOIL_REPORT_MAX_MB``). Stored through the SHARED ``LocalFileStorage``
class with a separate root — same opaque-reference contract, no new
abstraction.
"""

from __future__ import annotations

import io

from fastapi import status
from PIL import Image

from app.core.errors import AppError

PDF_MAGIC = b"%PDF-"


def detect_report_kind(data: bytes) -> str:
    """Return ``pdf`` | ``jpg`` | ``png``; raise 422 on anything else."""
    if not data:
        raise AppError(
            "Empty report file.",
            code="REPORT_INVALID_TYPE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if data.startswith(PDF_MAGIC):
        return "pdf"
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
        reopened = Image.open(io.BytesIO(data))
        fmt = (reopened.format or "").upper()
    except Exception:
        raise AppError(
            "Unsupported report. Upload a PDF, JPG, or PNG file.",
            code="REPORT_INVALID_TYPE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from None
    if fmt in {"JPEG", "JPG"}:
        return "jpg"
    if fmt == "PNG":
        return "png"
    raise AppError(
        "Unsupported report. Upload a PDF, JPG, or PNG file.",
        code="REPORT_INVALID_TYPE",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def validate_report_bytes(data: bytes, *, max_mb: int) -> str:
    """Size-cap + magic-byte validation → detected kind (``pdf|jpg|png``)."""
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(
            f"Report is too large (max {max_mb} MB).",
            code="REPORT_TOO_LARGE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return detect_report_kind(data)


REPORT_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "png": "image/png",
}
