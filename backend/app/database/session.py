"""Database engine, session factory and declarative base for InferSight."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
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
    _apply_lightweight_migrations(SessionLocal)

    from app.services.auth_service import ensure_admin

    ensure_admin(SessionLocal())


def _apply_lightweight_migrations(db_factory) -> None:
    """Add columns introduced after a table's initial create.

    create_all never alters existing tables, so a deployed Postgres database
    predating a new column would otherwise fail at runtime. SQLite does not
    support ADD COLUMN IF NOT EXISTS, so the columns are checked via PRAGMA
    first; failures are non-fatal so a fresh database stays untouched.
    """
    sqlite_columns = [
        ("datasets", "last_import_at", "TIMESTAMP WITH TIME ZONE"),
        ("dataset_versions", "filename", "VARCHAR(255)"),
        (
            "dataset_versions",
            "status",
            "VARCHAR(32) NOT NULL DEFAULT 'success'",
        ),
    ]
    postgres_statements = [
        "ALTER TABLE datasets ADD COLUMN IF NOT EXISTS last_import_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE dataset_versions ADD COLUMN IF NOT EXISTS filename VARCHAR(255)",
        "ALTER TABLE dataset_versions ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'success'",
    ]

    dialect = engine.dialect.name
    with db_factory() as db:
        for statement in postgres_statements if dialect != "sqlite" else []:
            try:
                db.execute(text(statement))
                db.commit()
            except Exception:
                db.rollback()
        if dialect == "sqlite":
            for table, column, definition in sqlite_columns:
                existing = set(
                    row[1]
                    for row in db.execute(text(f"PRAGMA table_info({table})")).all()
                )
                if column not in existing:
                    try:
                        db.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                            )
                        )
                        db.commit()
                    except Exception:
                        db.rollback()
