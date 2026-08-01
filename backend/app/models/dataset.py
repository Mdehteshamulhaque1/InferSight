"""Dataset and time-series point ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metric_type: Mapped[str] = mapped_column(String(64), default="revenue")
    unit: Mapped[str] = mapped_column(String(32), default="count")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    granularity: Mapped[str] = mapped_column(String(16), default="day")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner = relationship("User", back_populates="datasets")
    organization = relationship("Organization", back_populates="datasets")
    points = relationship(
        "MetricPoint",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    insights = relationship(
        "Insight",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    alerts = relationship(
        "Alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="dataset",
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_dataset_owner_slug"),
    )


class MetricPoint(Base):
    __tablename__ = "metric_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset = relationship("Dataset", back_populates="points")

    __table_args__ = (
        UniqueConstraint("dataset_id", "timestamp", name="uq_point_dataset_timestamp"),
    )
