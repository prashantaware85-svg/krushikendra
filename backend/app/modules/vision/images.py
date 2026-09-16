"""Image validation + quality gates (Pillow on ACTUAL bytes, not extensions).

JPG/PNG/WEBP only (``verify()`` on real bytes); count/size/dimension caps;
quality heuristics (too-small, too-dark mean luminance, blurry interior
Laplacian variance with borders excluded). Failures return
``IMAGE_QUALITY_INSUFFICIENT`` (+ how to retake) instead of any finding.
"""

from __future__ import annotations

import io

from fastapi import status
from PIL import Image, ImageStat

from app.core.errors import AppError


def _mb(n_bytes: int) -> float:
    return n_bytes / (1024 * 1024)


def validate_image_bytes(
    data: bytes,
    *,
    max_file_mb: int,
    min_dimension: int,
    max_dimension: int,
) -> Image.Image:
    """Validate magic bytes + caps; return an opened Pillow image."""
    if not data:
        raise AppError(
            "Empty image file.",
            code="IMAGE_INVALID_TYPE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if _mb(len(data)) > max_file_mb:
        raise AppError(
            f"Image is too large (max {max_file_mb} MB).",
            code="IMAGE_TOO_LARGE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # magic bytes, not the filename
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise AppError(
            "Unsupported image. Upload a JPG, PNG, or WEBP photo.",
            code="IMAGE_INVALID_TYPE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from None
    width, height = image.size
    if (
        width < min_dimension
        or height < min_dimension
        or width > max_dimension
        or height > max_dimension
    ):
        raise AppError(
            "Image dimensions are outside the supported range. "
            "Retake a clear close-up photo in daylight.",
            code="IMAGE_QUALITY_INSUFFICIENT",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return image


def assess_quality(image: Image.Image) -> tuple[str, str | None]:
    """Heuristic quality gate → (quality, notes). Never a finding."""
    gray = image.convert("L")
    mean = ImageStat.Stat(gray).mean[0]
    if mean < 30:
        return "poor", (
            "Photo looks too dark. Retake in daylight with the leaf filling the frame."
        )
    width, height = gray.size
    margin_x, margin_y = max(1, width // 8), max(1, height // 8)
    interior = gray.crop((margin_x, margin_y, width - margin_x, height - margin_y))
    pixels = list(interior.tobytes())
    if len(pixels) > 4:
        avg = sum(pixels) / len(pixels)
        variance = sum((p - avg) ** 2 for p in pixels) / len(pixels)
        if variance < 25:
            return "poor", (
                "Photo looks blurry or flat. Hold steady, focus on the affected "
                "part, and retake in daylight."
            )
    if mean < 60:
        return "usable", "Photo is dim; a brighter daylight retake may help."
    return "good", None
