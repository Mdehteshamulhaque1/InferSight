"""Dataset versioning and audit-trail ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DatasetVersion(Base):
    """Immutable snapshot of a dataset's point set at a point in time.

    `snapshot` stores the full `{iso_timestamp: value}` mapping so an earlier
    version can be restored on rollback. Storing the mapping (not SQL rows)
    keeps rollback a single transaction: clear points, bulk insert the snapshot.
    """

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(32), default="ingest")
    points_added: Mapped[int] = mapped_column(default=0)
    points_removed: Mapped[int] = mapped_column(default=0)
    total_after: Mapped[int] = mapped_column(default=0)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="success")
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset = relationship("Dataset")

    __table_args__ = (
        UniqueConstraint("dataset_id", "version_no", name="uq_version_dataset_no"),
    )


class AuditEvent(Base):
    """Append-only trail of who did what, when — per-user and per-dataset."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(32), default="dataset")
    resource_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
