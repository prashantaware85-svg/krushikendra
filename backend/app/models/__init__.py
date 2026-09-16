"""Krushi Seva models package — every table is registered here.

Importing this package registers all models on ``app.db.base.Base.metadata``
(Alembic ``env.py`` and tests both rely on that side effect).
"""

from app.models import (  # noqa: F401
    activity,
    ai,
    auth,
    commerce,
    crop,
    farm,
    inventory,
    khata,
    market,
    payments,
    pest,
    pos,
    rag,
    soil,
    staff,
    store,
    system,
    vision,
    weather,
)
