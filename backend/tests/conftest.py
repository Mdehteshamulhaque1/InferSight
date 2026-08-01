"""Shared pytest fixtures.

The test database is an isolated in-memory SQLite instance bound to a static
connection pool so a single engine/connection is shared across the app and the
dependency override — this is the canonical pattern for FastAPI + SQLAlchemy
test isolation.
"""

from __future__ import annotations

import os
from collections.abc import Generator

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdefghijklmnopqrstuvwxyz")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("CELERY_ENABLED", "false")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.dev")
os.environ.setdefault("ADMIN_PASSWORD", "admin12345")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database.session import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Reset the shared cache between tests for rate-limit/cache isolation."""
    from app.services.cache import cache_service

    cache_service._local.clear()
    yield


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    from app.services.auth_service import create_user

    create_user(db_session, "admin@test.dev", "admin12345", "Test Admin", role="admin")

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.dev", "password": "admin12345"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst@test.dev",
            "password": "Password123",
            "full_name": "Test Analyst",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_series(start="2026-01-01", days=45, base=100.0, step=2.0, seed=1):
    """Generate a deterministic daily series used across tests."""
    import random
    from datetime import datetime, timedelta, timezone

    rng = random.Random(seed)
    start_ts = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    points = []
    for i in range(days):
        value = base + step * i + rng.uniform(-3, 3)
        points.append(
            {
                "timestamp": (start_ts + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "value": round(value, 2),
            }
        )
    return points


@pytest.fixture()
def seeded_dataset(client: TestClient, user_headers: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={
            "name": "Test Revenue",
            "slug": "test-revenue",
            "metric_type": "revenue",
            "unit": "USD",
            "currency": "USD",
            "granularity": "day",
        },
    )
    assert resp.status_code == 201, resp.text
    dataset_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/points",
        headers=user_headers,
        json={"points": make_series()},
    )
    assert resp.status_code == 200, resp.text
    return dataset_id
