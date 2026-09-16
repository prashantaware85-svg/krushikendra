"""Crop-image policy: validate → store → observe (uncertain) → contract.

Sync flow (a worker queue is the documented future path). Provider failure →
row ``failed`` + safe 503; nothing fabricated, internals never exposed.
RAG supporting-info lookup attaches VERIFIED-doc citations as "general
supporting information" — it can NEVER upgrade uncertainty.
"""

from __future__ import annotations

import io
import json
import logging
import uuid

from fastapi import status
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.vision import CropImageAnalysis
from app.modules.ai.retrieval import chunk_to_source, similar_chunks
from app.modules.ai.providers import get_embedding_provider
from app.modules.common.storage import LocalFileStorage
from app.modules.vision import repository
from app.modules.vision.images import assess_quality, validate_image_bytes
from app.modules.vision.providers import (
    ProviderError,
    VisionResult,
    disclaimer_for,
    get_vision_provider,
)

logger = logging.getLogger("krushi-seva.vision")

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().vision_storage_dir)


def _not_found() -> AppError:
    return AppError(
        "Crop image analysis not found.",
        code="ANALYSIS_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _serialize(row: CropImageAnalysis) -> dict:
    def _load(raw: str | None) -> list:
        try:
            data = json.loads(raw or "[]")
        except (ValueError, TypeError):
            return []
        return data if isinstance(data, list) else []

    return {
        "id": row.id,
        "farm_id": row.farm_id,
        "farm_crop_id": row.farm_crop_id,
        "status": row.status,
        "provider": row.provider,
        "model": row.model_name,
        "possible_condition": row.possible_condition,
        "confidence": None if row.confidence is None else str(row.confidence),
        "observations": _load(row.observations_json),
        "needs_info": _load(row.needs_info_json),
        "next_steps": _load(row.next_steps_json),
        "image_quality": row.image_quality,
        "quality_notes": row.quality_notes,
        "disclaimer": disclaimer_for(row.response_language or "mr"),
        "sources": _load(row.sources_json),
        "response_language": row.response_language or "mr",
        "is_mock": bool(row.is_mock),
    }


def _run_analysis(
    db: Session, row: CropImageAnalysis, image_bytes: list[bytes], crop_name: str | None = None
) -> CropImageAnalysis:
    settings = get_settings()
    row.status = "processing"
    db.commit()
    try:
        result: VisionResult = get_vision_provider().analyze_crop_image(
            image_bytes, row.response_language or "mr", crop_name
        )
    except ProviderError as exc:
        row.status = "failed"
        db.commit()
        raise AppError(
            "Analysis service is unavailable. Your photos are saved — retry is possible.",
            code="VISION_PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    row.possible_condition = result.possible_condition
    row.confidence = result.confidence
    row.observations_json = json.dumps(result.observations)
    row.needs_info_json = json.dumps(result.needs_info)
    row.next_steps_json = json.dumps(result.next_steps)
    row.image_quality = result.quality
    row.is_mock = result.is_mock
    # RAG supporting info (verified docs only; empty KB → sources []).
    try:
        query = " ".join(
            [result.possible_condition or "", *result.observations]
        ).strip()
        vector = get_embedding_provider().generate_embedding(query)
        hits = similar_chunks(
            db,
            vector,
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_min_similarity,
            candidate_limit=settings.rag_candidate_limit,
        )
        row.sources_json = json.dumps([chunk_to_source(h) for h in hits])
    except ProviderError:
        row.sources_json = json.dumps([])
    row.status = "completed"
    return repository.save(db, row)


def _check_rate_limit(db: Session, farmer_id: uuid.UUID) -> None:
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    count = (
        db.query(CropImageAnalysis)
        .filter(
            CropImageAnalysis.farmer_user_id == farmer_id,
            CropImageAnalysis.created_at >= since,
        )
        .count()
    )
    if count >= settings.vision_max_analyses_per_hour:
        raise AppError(
            "Hourly analysis limit reached. Please try again later.",
            code="VISION_RATE_LIMITED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _thumbnail(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data)).convert("RGB")
    image.thumbnail((256, 256))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def upload_and_analyze(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID | None,
    language: str,
    files: list[tuple[str, bytes]],
) -> dict:
    """Validate 1–3 photos, store, observe (sync) → safe response contract."""
    settings = get_settings()
    if not files or len(files) > settings.vision_max_images:
        raise AppError(
            f"Upload 1 to {settings.vision_max_images} photos.",
            code="IMAGE_TOO_MANY",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    _check_rate_limit(db, farmer_id)

    storage = _storage()
    validated: list[bytes] = []
    for filename, data in files:
        suffix = "." + (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
        image = validate_image_bytes(
            data,
            max_file_mb=settings.vision_max_file_mb,
            min_dimension=settings.vision_min_dimension,
            max_dimension=settings.vision_max_dimension,
        )
        quality, notes = assess_quality(image)
        if quality == "poor":
            raise AppError(
                notes or "Photo quality is insufficient. Retake in daylight.",
                code="IMAGE_QUALITY_INSUFFICIENT",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        validated.append(data)
        _ = suffix  # suffix is informational; bytes decide the stored format

    refs = [storage.save_bytes(data, ".jpg") for data in validated]
    thumb_ref = storage.save_bytes(_thumbnail(validated[0]), ".jpg")
    row = repository.create_analysis(
        db,
        farmer_user_id=farmer_id,
        farm_id=farm_id,
        farm_crop_id=crop_id,
        image_path=refs[0],
        thumbnail_path=thumb_ref,
        extra_image_references=json.dumps(refs[1:]),
        status="pending",
        provider=settings.vision_provider,
        model_name=settings.vision_model,
        is_mock=settings.vision_provider == "mock",
        response_language=language,
    )
    row = _run_analysis(db, row, validated)
    logger.info("vision_upload farmer=%s status=%s", farmer_id, row.status)
    return _serialize(row)


def list_analyses(db: Session, *, farmer_id: uuid.UUID) -> list[dict]:
    """Own history, newest, bounded (no refs/paths/secrets)."""
    items = []
    for row in repository.list_owned(db, farmer_id=farmer_id):
        items.append(
            {
                "id": row.id,
                "farm_id": row.farm_id,
                "farm_crop_id": row.farm_crop_id,
                "crop_name": None,
                "status": row.status,
                "possible_condition": row.possible_condition,
                "confidence": None if row.confidence is None else str(row.confidence),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        )
    return items


def get_analysis(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID
) -> dict:
    """Owned result contract."""
    row = repository.get_owned(db, farmer_id=farmer_id, analysis_id=analysis_id)
    if row is None:
        raise _not_found()
    return _serialize(row)


def get_image_bytes(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID
) -> tuple[bytes, str]:
    """Owned primary-image bytes (+ media type from stored suffix)."""
    row = repository.get_owned(db, farmer_id=farmer_id, analysis_id=analysis_id)
    if row is None:
        raise _not_found()
    data = _storage().read_bytes(row.image_path)
    if data is None:
        raise AppError(
            "Image file is no longer available.",
            code="IMAGE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    suffix = row.image_path.rsplit(".", 1)[-1].lower() if "." in row.image_path else "jpg"
    media = {"png": "image/png", "webp": "image/webp"}.get(suffix, "image/jpeg")
    return data, media


def reanalyze(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID
) -> dict:
    """Idempotent re-run (reads stored bytes, same uncertain contract)."""
    row = repository.get_owned(db, farmer_id=farmer_id, analysis_id=analysis_id)
    if row is None:
        raise _not_found()
    storage = _storage()
    refs = [row.image_path, *json.loads(row.extra_image_references or "[]")]
    payloads = [storage.read_bytes(ref) for ref in refs]
    payloads = [p for p in payloads if p is not None]
    if not payloads:
        raise AppError(
            "Image file is no longer available.",
            code="IMAGE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    row = _run_analysis(db, row, payloads)
    return _serialize(row)


def delete_analysis(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID
) -> None:
    """Soft-delete the row + remove files best-effort."""
    row = repository.get_owned(db, farmer_id=farmer_id, analysis_id=analysis_id)
    if row is None:
        raise _not_found()
    row.is_active = False
    db.commit()
    storage = _storage()
    storage.delete(row.image_path)
    storage.delete(row.thumbnail_path)
    try:
        for ref in json.loads(row.extra_image_references or "[]"):
            storage.delete(ref)
    except (ValueError, TypeError):
        pass
