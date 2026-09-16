"""DEV-ONLY bootstrap: grant the first store admin role (Step 17 RBAC).

Creates a ``store_staff`` admin row for an EXISTING login user (resolved by
mobile number). Never creates login accounts and never auto-promotes:
the target user must already exist (register/verify-OTP first).

Manual run only — never in production::

    python scripts/bootstrap_admin.py 9876543210
    python scripts/bootstrap_admin.py 9876543210 --role store_manager

Refuses to run when ``ENVIRONMENT=production``. Later admins are managed
via the ``/store/staff`` API (admin-only) instead of this script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401  # register tables on Base.metadata
from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.inventory import DEFAULT_STORE_ID  # noqa: E402
from app.models.staff import STAFF_ROLES, StoreAuditLog, StoreStaff  # noqa: E402
from app.modules.auth.security import normalize_mobile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a store staff admin (dev-only).")
    parser.add_argument("mobile", help="10-digit mobile of an EXISTING login user")
    parser.add_argument(
        "--role",
        default="admin",
        choices=list(STAFF_ROLES),
        help="staff role to grant (default: admin)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_production:
        print("REFUSED: bootstrap_admin never runs in production.")
        return 1

    mobile = normalize_mobile(args.mobile)
    factory = get_session_factory()
    with factory() as db:
        user = db.scalar(select(User).where(User.mobile_number == mobile))
        if user is None:
            print(f"No login user with mobile {mobile} — register/verify-OTP first.")
            return 1
        existing = db.scalar(
            select(StoreStaff).where(
                StoreStaff.store_id == DEFAULT_STORE_ID,
                StoreStaff.user_id == user.id,
            )
        )
        if existing is not None:
            print(
                f"User {mobile} is already staff "
                f"(role={existing.role}, active={existing.is_active}) — nothing to do."
            )
            return 0
        row = StoreStaff(
            store_id=DEFAULT_STORE_ID,
            user_id=user.id,
            role=args.role,
            is_active=True,
        )
        db.add(row)
        db.flush()
        db.add(
            StoreAuditLog(
                store_id=DEFAULT_STORE_ID,
                actor_user_id=user.id,
                target_user_id=user.id,
                action="staff_create",
                old_role=None,
                new_role=args.role,
                old_active=None,
                new_active=True,
            )
        )
        db.commit()
        print(f"Granted role={args.role} to user {mobile} (self-bootstrap audit).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
