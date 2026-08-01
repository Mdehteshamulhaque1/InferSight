"""Alert rule and alert delivery schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.alert import AlertChannel, DeliveryStatus, SeverityLevel
from app.schemas.common import ORMModel


class AlertRuleCreate(BaseModel):
    dataset_id: int
    severity_threshold: SeverityLevel = SeverityLevel.WARNING
    channels: list[AlertChannel] = Field(default_factory=lambda: [AlertChannel.EMAIL])
    cooldown_minutes: int = Field(default=30, ge=1, le=10080)
    is_active: bool = True
    webhook_url: str | None = Field(default=None, max_length=512)

    @field_validator("channels")
    @classmethod
    def channels_not_empty(cls, value: list[AlertChannel]) -> list[AlertChannel]:
        if not value:
            raise ValueError("at least one channel is required")
        return value


class AlertRuleUpdate(BaseModel):
    severity_threshold: SeverityLevel | None = None
    channels: list[AlertChannel] | None = None
    cooldown_minutes: int | None = Field(default=None, ge=1, le=10080)
    is_active: bool | None = None
    webhook_url: str | None = Field(default=None, max_length=512)

    @field_validator("channels")
    @classmethod
    def channels_not_empty(
        cls, value: list[AlertChannel] | None
    ) -> list[AlertChannel] | None:
        if value is not None and not value:
            raise ValueError("at least one channel is required")
        return value


class AlertRuleOut(ORMModel):
    id: int
    dataset_id: int
    severity_threshold: SeverityLevel
    channels: list[AlertChannel]
    cooldown_minutes: int
    is_active: bool
    webhook_url: str | None
    created_at: datetime


class AlertDeliveryOut(ORMModel):
    id: int
    alert_id: int
    rule_id: int | None
    channel: str
    status: DeliveryStatus
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime
