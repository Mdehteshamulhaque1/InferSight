"""Alert ORM models — persisted notifications, routing rules, and deliveries.

Includes the in-app ``Alert`` feed entry plus the ``AlertRule`` (a routing
configuration tied to a dataset) and ``AlertDelivery`` (one attempt to notify
a channel about an alert) rows used by the alert-routing pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SeverityLevel(str, Enum):
    """Alert severity threshold used by routing rules."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Notification channels an alert rule can deliver over."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"


class DeliveryStatus(str, Enum):
    """Lifecycle state of a single channel delivery attempt."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AlertRule(Base):
    """Routing rule: which anomalies on a dataset should notify, and how.

    ``channels`` is a JSON list drawn from :class:`AlertChannel`. ``webhook_url``
    is required for the ``webhook`` channel and is a per-rule destination.
    """

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    severity_threshold: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel), default=SeverityLevel.WARNING
    )
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset = relationship("Dataset")
    deliveries = relationship(
        "AlertDelivery",
        back_populates="rule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AlertDelivery(Base):
    """A single delivery attempt for an alert over one channel.

    ``rule_id`` links the attempt back to the rule that produced it so cooldown
    checks and escalation can scope per (dataset, rule).
    """

    __tablename__ = "alert_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"), index=True, nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus), default=DeliveryStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    alert = relationship("Alert")
    rule = relationship("AlertRule", back_populates="deliveries")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="anomaly")
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(1024))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset = relationship("Dataset")

    __table_args__ = (
        # Keep the same event from fanning into duplicate alerts.
        UniqueConstraint(
            "dataset_id", "kind", "title", name="uq_alert_dedupe"
        ),
    )
