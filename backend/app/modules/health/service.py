"""Health policy: track observations + recorded actions (never treatment).

Business rules: ``unknown`` type carries NO catalogue links (422 on create
AND on type-changing updates); catalogue links must be live + active
(404 ``PEST_INVALID`` / ``DISEASE_INVALID`` — no oracle); analysis links
must be live + farmer-owned (404 ``ANALYSIS_LINK_INVALID``). Severity is
display-only — this module contains no severity→treatment branch by design.
Photos reuse the shared ``LocalFileStorage`` class with a dedicated root.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.pest import CropHealthObservation, Disease, HealthAction, Pest
from app.models.vision import CropImageAnalysis
from app.modules.common.storage import LocalFileStorage
from app.modules.health import repository
from app.modules.vision.images import validate_image_bytes


def _storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().health_storage_dir)


def _obs_not_found() -> AppError:
    return AppError(
        "Health observation not found.",
        code="OBSERVATION_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _action_not_found() -> AppError:
    return AppError(
        "Health action not found.",
        code="ACTION_NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _check_catalogue_link(
    db: Session, model, row_id: uuid.UUID | None, *, kind: str
) -> None:
    if row_id is None:
        return
    if repository.get_catalogue_row(db, model, row_id) is None:
        code = "PEST_INVALID" if kind == "pest" else "DISEASE_INVALID"
        raise AppError(
            f"Unknown {kind} reference.",
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _check_type_links(observation_type: str, pest_id, disease_id) -> None:
    if observation_type == "unknown" and (pest_id or disease_id):
        raise AppError(
            "Observations of type 'unknown' cannot link catalogue entries.",
            code="OBSERVATION_TYPE_MISMATCH",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _check_analysis_link(
    db: Session, *, farmer_id: uuid.UUID, analysis_id: uuid.UUID | None
) -> None:
    if analysis_id is None:
        return
    row = (
        db.query(CropImageAnalysis)
        .filter(
            CropImageAnalysis.id == analysis_id,
            CropImageAnalysis.farmer_user_id == farmer_id,
            CropImageAnalysis.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise AppError(
            "Unknown image analysis reference.",
            code="ANALYSIS_LINK_INVALID",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _photo_refs(row: CropHealthObservation) -> list[str]:
    try:
        data = json.loads(row.photo_references or "[]")
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _linked_summary(db: Session, row: CropHealthObservation) -> dict | None:
    if row.linked_analysis_id is None:
        return None
    analysis = db.get(CropImageAnalysis, row.linked_analysis_id)
    if analysis is None or not analysis.is_active:
        return None
    return {
        "id": analysis.id,
        "possible_condition": analysis.possible_condition,
        "confidence": None if analysis.confidence is None else str(analysis.confidence),
        "status": analysis.status,
    }


def _serialize_obs(db: Session, row: CropHealthObservation) -> dict:
    return {
        "id": row.id,
        "farm_crop_id": row.farm_crop_id,
        "observation_type": row.observation_type,
        "pest_id": row.pest_id,
        "pest_name": repository.catalogue_name(db, Pest, row.pest_id),
        "disease_id": row.disease_id,
        "disease_name": repository.catalogue_name(db, Disease, row.disease_id),
        "observed_name": row.observed_name,
        "observation_date": row.observed_on,
        "severity": row.severity or "unknown",
        "affected_area": None if row.affected_area is None else str(row.affected_area),
        "affected_area_unit": row.affected_area_unit,
        "symptoms": row.symptoms,
        "notes": row.notes,
        "status": row.status,
        "source": row.source,
        "has_photos": bool(_photo_refs(row)),
        "linked_analysis": _linked_summary(db, row),
    }


def _serialize_action(row: HealthAction) -> dict:
    return {
        "id": row.id,
        "observation_id": row.observation_id,
        "action_date": row.acted_on,
        "action_type": row.action_type,
        "description": row.description,
        "product_name": row.product_name,
        "quantity": None if row.quantity is None else str(row.quantity),
        "quantity_unit": row.quantity_unit,
        "notes": row.notes,
    }


# ── Catalogue (information labels, never a diagnosis) ──────────────────────

def list_pests(db: Session) -> list[dict]:
    """Active pest rows with the verified flag exposed."""
    return [
        {
            "id": r.id, "name": r.name, "local_name": r.local_name,
            "scientific_name": r.scientific_name, "category": r.category,
            "description": r.description, "is_verified": r.is_verified,
        }
        for r in repository.list_catalogue(db, Pest)
    ]


def list_diseases(db: Session) -> list[dict]:
    """Active disease rows with the verified flag exposed."""
    return [
        {
            "id": r.id, "name": r.name, "local_name": r.local_name,
            "scientific_name": r.scientific_name, "category": r.category,
            "description": r.description, "is_verified": r.is_verified,
        }
        for r in repository.list_catalogue(db, Disease)
    ]


# ── Observations ───────────────────────────────────────────────────────────

def list_observations(
    db: Session, *, farmer_id: uuid.UUID, farm_id: uuid.UUID, crop_id: uuid.UUID
) -> list[dict]:
    return [
        _serialize_obs(db, row)
        for row in repository.list_observations(
            db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id
        )
    ]


def create_observation(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    payload: dict,
) -> dict:
    """Record farmer-observed facts verbatim (never parsed into a diagnosis)."""
    _check_type_links(
        payload.get("observation_type", "unknown"),
        payload.get("pest_id"),
        payload.get("disease_id"),
    )
    _check_catalogue_link(db, Pest, payload.get("pest_id"), kind="pest")
    _check_catalogue_link(db, Disease, payload.get("disease_id"), kind="disease")
    _check_analysis_link(
        db, farmer_id=farmer_id, analysis_id=payload.get("linked_image_analysis_id")
    )
    row = repository.create_observation(
        db,
        farmer_user_id=farmer_id,
        farm_id=farm_id,
        farm_crop_id=crop_id,
        observation_type=payload.get("observation_type", "unknown"),
        pest_id=payload.get("pest_id"),
        disease_id=payload.get("disease_id"),
        observed_name=payload.get("observed_name"),
        observed_on=payload.get("observation_date"),
        severity=payload.get("severity", "unknown"),
        affected_area=payload.get("affected_area"),
        affected_area_unit=payload.get("affected_area_unit"),
        symptoms=payload.get("symptoms"),
        notes=payload.get("notes"),
        status=payload.get("status", "observed"),
        source=payload.get("source", "farmer"),
        linked_analysis_id=payload.get("linked_image_analysis_id"),
    )
    return _serialize_obs(db, row)


def get_observation(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
) -> dict:
    row = repository.get_owned_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    if row is None:
        raise _obs_not_found()
    return _serialize_obs(db, row)


def update_observation(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    patch: dict,
) -> dict:
    """Plain PUT updates (status transitions included); type rule re-checked."""
    row = repository.get_owned_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    if row is None:
        raise _obs_not_found()
    new_type = patch.get("observation_type", row.observation_type)
    new_pest = patch.get("pest_id", row.pest_id)
    new_disease = patch.get("disease_id", row.disease_id)
    _check_type_links(new_type, new_pest, new_disease)
    _check_catalogue_link(db, Pest, patch.get("pest_id"), kind="pest")
    _check_catalogue_link(db, Disease, patch.get("disease_id"), kind="disease")
    if "linked_image_analysis_id" in patch:
        _check_analysis_link(
            db, farmer_id=farmer_id, analysis_id=patch["linked_image_analysis_id"]
        )
    mapping = {
        "observation_type": "observation_type",
        "pest_id": "pest_id",
        "disease_id": "disease_id",
        "observed_name": "observed_name",
        "observation_date": "observed_on",
        "severity": "severity",
        "affected_area": "affected_area",
        "affected_area_unit": "affected_area_unit",
        "symptoms": "symptoms",
        "notes": "notes",
        "status": "status",
        "source": "source",
        "linked_image_analysis_id": "linked_analysis_id",
    }
    for key, column in mapping.items():
        if key in patch:
            setattr(row, column, patch[key])
    return _serialize_obs(db, repository.save_observation(db, row))


def delete_observation(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
) -> None:
    """Soft-delete; photo files removed best-effort."""
    row = repository.get_owned_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    if row is None:
        raise _obs_not_found()
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    storage = _storage()
    for ref in _photo_refs(row):
        storage.delete(ref)


def upload_photos(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    files: list[tuple[str, bytes]],
) -> dict:
    """Attach up to 3 photos (magic bytes + Step 10 gates; ``has_photos`` only)."""
    row = repository.get_owned_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    if row is None:
        raise _obs_not_found()
    settings = get_settings()
    refs = _photo_refs(row)
    if len(refs) + len(files) > settings.vision_max_images or not files:
        raise AppError(
            f"Attach 1 to {settings.vision_max_images} photos per observation.",
            code="IMAGE_TOO_MANY",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    storage = _storage()
    for _filename, data in files:
        image = validate_image_bytes(
            data,
            max_file_mb=settings.vision_max_file_mb,
            min_dimension=settings.vision_min_dimension,
            max_dimension=settings.vision_max_dimension,
        )
        from app.modules.vision.images import assess_quality

        quality, notes = assess_quality(image)
        if quality == "poor":
            raise AppError(
                notes or "Photo quality is insufficient. Retake in daylight.",
                code="IMAGE_QUALITY_INSUFFICIENT",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        refs.append(storage.save_bytes(data, ".jpg"))
    row.photo_references = json.dumps(refs)
    return _serialize_obs(db, repository.save_observation(db, row))


def get_photo_bytes(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID,
    observation_id: uuid.UUID,
    index: int,
) -> tuple[bytes, str]:
    """Owned photo bytes (authed — no public URLs by design)."""
    row = repository.get_owned_observation(
        db, farmer_id=farmer_id, farm_id=farm_id, crop_id=crop_id,
        observation_id=observation_id,
    )
    if row is None:
        raise _obs_not_found()
    refs = _photo_refs(row)
    if index < 0 or index >= len(refs):
        raise AppError(
            "Photo not found.", code="PHOTO_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    data = _storage().read_bytes(refs[index])
    if data is None:
        raise AppError(
            "Photo file is no longer available.", code="PHOTO_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return data, "image/jpeg"


# ── Actions (recorded facts, never system output) ──────────────────────────

def _owned_observation_for_actions(
    db: Session, *, farmer_id: uuid.UUID, observation_id: uuid.UUID
) -> CropHealthObservation:
    row = repository.get_owned_observation_by_id(
        db, farmer_id=farmer_id, observation_id=observation_id
    )
    if row is None:
        raise _obs_not_found()
    return row


def list_actions(
    db: Session, *, farmer_id: uuid.UUID, observation_id: uuid.UUID
) -> list[dict]:
    _owned_observation_for_actions(db, farmer_id=farmer_id, observation_id=observation_id)
    return [
        _serialize_action(row)
        for row in repository.list_actions(db, observation_id=observation_id)
    ]


def create_action(
    db: Session, *, farmer_id: uuid.UUID, observation_id: uuid.UUID, payload: dict
) -> dict:
    """Record "what was done" (a recorded chemical_application with a product
    name is a farmer report — no dosage is ever generated or validated)."""
    _owned_observation_for_actions(db, farmer_id=farmer_id, observation_id=observation_id)
    row = repository.create_action(
        db,
        observation_id=observation_id,
        action_type=payload["action_type"],
        description=payload.get("description"),
        product_name=payload.get("product_name"),
        quantity=payload.get("quantity"),
        quantity_unit=payload.get("quantity_unit"),
        acted_on=payload.get("action_date"),
        notes=payload.get("notes"),
    )
    return _serialize_action(row)


def update_action(
    db: Session,
    *,
    farmer_id: uuid.UUID,
    observation_id: uuid.UUID,
    action_id: uuid.UUID,
    patch: dict,
) -> dict:
    _owned_observation_for_actions(db, farmer_id=farmer_id, observation_id=observation_id)
    row = repository.get_owned_action(
        db, observation_id=observation_id, action_id=action_id
    )
    if row is None:
        raise _action_not_found()
    mapping = {
        "action_type": "action_type",
        "description": "description",
        "product_name": "product_name",
        "quantity": "quantity",
        "quantity_unit": "quantity_unit",
        "action_date": "acted_on",
        "notes": "notes",
    }
    for key, column in mapping.items():
        if key in patch:
            setattr(row, column, patch[key])
    return _serialize_action(repository.save_action(db, row))


def delete_action(
    db: Session, *, farmer_id: uuid.UUID, observation_id: uuid.UUID, action_id: uuid.UUID
) -> None:
    _owned_observation_for_actions(db, farmer_id=farmer_id, observation_id=observation_id)
    row = repository.get_owned_action(
        db, observation_id=observation_id, action_id=action_id
    )
    if row is None:
        raise _action_not_found()
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
