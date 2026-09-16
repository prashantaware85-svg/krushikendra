"""DEV-ONLY sample catalogue seed (Step 13 rebuild).

Unverified display rows with NULL (price-on-request) prices included.
Manual run only — never in production::

    python scripts/seed_store_sample.py

Refuses to run when ``ENVIRONMENT=production``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.models.store import (  # noqa: E402
    Product,
    ProductCategory,
    ProductImage,
    ProductVariant,
)
from app.modules.common.storage import LocalFileStorage  # noqa: E402

# 1x1 transparent PNG (placeholder bytes so the image route resolves).
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def main() -> int:
    settings = get_settings()
    if settings.is_production:
        print("REFUSED: seed scripts never run in production.")
        return 1

    factory = get_session_factory()
    storage = LocalFileStorage(settings.store_storage_dir)
    with factory() as db:
        existing = db.scalar(
            select(ProductCategory).where(ProductCategory.name == "Seeds")
        )
        if existing is not None:
            print("Seed already present (category 'Seeds' exists) — nothing to do.")
            return 0

        category = ProductCategory(
            name="Seeds", description="DEV-ONLY unverified sample catalogue."
        )
        db.add(category)
        db.flush()

        cotton = Product(
            name="Sample Cotton Seeds",
            description="DEV-ONLY unverified row.",
            category_id=category.id,
            base_price_paise=25000,
            is_active=True,
        )
        binder = Product(
            name="Sample Binder (price on request)",
            description="DEV-ONLY unverified row with NULL prices.",
            category_id=category.id,
            base_price_paise=None,
            is_active=True,
        )
        db.add_all([cotton, binder])
        db.flush()

        db.add_all(
            [
                ProductVariant(
                    product_id=cotton.id,
                    name="1 kg pack",
                    price_paise=25000,
                    stock_qty=10,
                ),
                ProductVariant(
                    product_id=binder.id,
                    name="Standard pack",
                    price_paise=None,  # NULL → unorderable, 422 at checkout
                    stock_qty=5,
                ),
            ]
        )
        reference = storage.save_bytes(_TINY_PNG, ".png")
        db.add(
            ProductImage(
                product_id=cotton.id,
                image_path=reference,
                alt_text="DEV-ONLY sample image.",
            )
        )
        db.commit()
        print("Seeded 1 category, 2 products (1 NULL-priced), 2 variants, 1 image.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
