"""DEV-ONLY crop-variety catalogue seed (manual run, NEVER production).

Idempotent: re-runs skip existing (crop_name, variety_name) pairs.
Reference labels only — never advice.

Usage:
    python scripts/seed_crop_varieties.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.models.crop import CropVariety

SAMPLE_VARIETIES = [
    {"crop_name": "Wheat", "variety_name": "SAMPLE (dev only) Lokwan", "crop_category": "cereal", "season": "rabi"},
    {"crop_name": "Rice", "variety_name": "SAMPLE (dev only) Indrayani", "crop_category": "cereal", "season": "kharif"},
    {"crop_name": "Soybean", "variety_name": "SAMPLE (dev only) JS-335", "crop_category": "oilseed", "season": "kharif"},
    {"crop_name": "Cotton", "variety_name": "SAMPLE (dev only) Bunny Bt", "crop_category": "fibre", "season": "kharif"},
    {"crop_name": "Onion", "variety_name": "SAMPLE (dev only) Red", "crop_category": "vegetable", "season": "rabi"},
]


def main() -> int:
    if get_settings().environment == "production":
        print("REFUSED: never run dev seeds in production.")
        return 1
    factory = get_session_factory()
    inserted = skipped = 0
    with factory() as db:
        for row in SAMPLE_VARIETIES:
            exists = (
                db.query(CropVariety)
                .filter(
                    CropVariety.crop_name == row["crop_name"],
                    CropVariety.variety_name == row["variety_name"],
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            db.add(CropVariety(**row))
            inserted += 1
        db.commit()
    dispose_engine()
    print(f"crop varieties seed: inserted={inserted} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
