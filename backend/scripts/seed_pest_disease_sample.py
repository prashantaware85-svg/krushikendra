"""DEV-ONLY pest/disease catalogue sample seed (manual run, NEVER production).

Idempotent: re-runs skip existing names. Rows are UNVERIFIED with a
"SAMPLE (dev only)" marker, so sample data can never pass as trusted
catalogue data. Matching a row records "farmer picked this label" — never
a confirmed diagnosis.

Usage:
    python scripts/seed_pest_disease_sample.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.models.pest import Disease, Pest

SAMPLE_PESTS = [
    {
        "name": "SAMPLE (dev only) — Stem Borer",
        "local_name": "खोड किडा",
        "scientific_name": "Chilo partellus",
        "category": "insect",
        "description": "Unverified dev sample — not agronomic guidance.",
    },
    {
        "name": "SAMPLE (dev only) — Aphid",
        "local_name": "मावा",
        "scientific_name": "Aphis gossypii",
        "category": "insect",
        "description": "Unverified dev sample — not agronomic guidance.",
    },
    {
        "name": "SAMPLE (dev only) — White Grub",
        "local_name": "हुमणी",
        "scientific_name": "Holotrichia serrata",
        "category": "insect",
        "description": "Unverified dev sample — not agronomic guidance.",
    },
]

SAMPLE_DISEASES = [
    {
        "name": "SAMPLE (dev only) — Leaf Spot",
        "local_name": "पानावरील ठिपके",
        "scientific_name": None,
        "category": "fungal",
        "description": "Unverified dev sample — not a diagnosis.",
    },
    {
        "name": "SAMPLE (dev only) — Powdery Mildew",
        "local_name": "भुरी",
        "scientific_name": None,
        "category": "fungal",
        "description": "Unverified dev sample — not a diagnosis.",
    },
    {
        "name": "SAMPLE (dev only) — Leaf Curl",
        "local_name": "पान कुरतडणे",
        "scientific_name": None,
        "category": "viral",
        "description": "Unverified dev sample — not a diagnosis.",
    },
]


def main() -> int:
    if get_settings().environment == "production":
        print("REFUSED: never run dev seeds in production.")
        return 1
    factory = get_session_factory()
    inserted = skipped = 0
    with factory() as db:
        for row in SAMPLE_PESTS:
            if db.query(Pest).filter(Pest.name == row["name"]).first():
                skipped += 1
                continue
            db.add(Pest(**row, is_verified=False))
            inserted += 1
        for row in SAMPLE_DISEASES:
            if db.query(Disease).filter(Disease.name == row["name"]).first():
                skipped += 1
                continue
            db.add(Disease(**row, is_verified=False))
            inserted += 1
        db.commit()
    dispose_engine()
    print(f"pest/disease seed: inserted={inserted} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
