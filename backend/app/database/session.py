"""Database engine, session factory and declarative base for InferSight."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {"echo": settings.database_echo, "pool_pre_ping": True}
    # SQLite does not support thread-based pooling; use file/queue semantics.
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = _make_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session with lifecycle cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and seed the bootstrap administrator.

    Called on startup whenever AUTO_CREATE_TABLES is enabled (local dev and
    fresh production databases). Uses create_all so existing tables are never
    altered; for schema changes to a live database, run migrations manually.
    """
    # Import models so that metadata is fully populated before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.services.auth_service import ensure_admin

    ensure_admin(SessionLocal())
