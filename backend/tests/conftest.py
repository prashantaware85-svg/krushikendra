"""Rebuilt-domain test harness (SQLite + dependency overrides)."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENVIRONMENT", "test")

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.common.dependencies import get_current_farmer_id  # noqa: E402

import app.models  # noqa: E402,F401  # register all tables on Base.metadata


@pytest.fixture()
def farmer_a() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def farmer_b() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def current_farmer(farmer_a):
    """Mutable holder so tests can switch identity mid-test (scoping)."""
    return {"id": farmer_a}


@pytest.fixture()
def client(db_session, current_farmer):
    app = create_app()

    def override_db():
        yield db_session

    def override_farmer() -> uuid.UUID:
        return current_farmer["id"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_farmer_id] = override_farmer
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(farmer_id: uuid.UUID) -> dict:
    """Real Bearer access JWT (same scheme as the auth domain)."""
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(farmer_id), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}
