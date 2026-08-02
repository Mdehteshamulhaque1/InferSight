"""Dataset and metric point schemas."""

from __future__ import annotations

import re

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

VALID_GRANULARITIES = {"hour", "day", "week", "month"}
VALID_METRIC_TYPES = {"revenue", "transactions", "users", "traffic", "custom"}


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    metric_type: str = Field(default="revenue", max_length=64)
    unit: str = Field(default="count", max_length=32)
    currency: str = Field(default="USD", max_length=8)
    granularity: str = Field(default="day", max_length=16)
    organization_id: int | None = Field(default=None, description="attach to an organization (membership required)")

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = value.strip().lower()
        slug = re.sub(r"[^a-z0-9-_]+", "-", slug)
        slug = slug.strip("-")
        if not slug:
            raise ValueError("slug cannot be empty after normalization")
        return slug

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, value: str) -> str:
        if value not in VALID_GRANULARITIES:
            raise ValueError(f"granularity must be one of {sorted(VALID_GRANULARITIES)}")
        return value

    @field_validator("metric_type")
    @classmethod
    def validate_metric_type(cls, value: str) -> str:
        if value not in VALID_METRIC_TYPES:
            raise ValueError(f"metric_type must be one of {sorted(VALID_METRIC_TYPES)}")
        return value


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    metric_type: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=8)
    granularity: str | None = Field(default=None, max_length=16)
    is_active: bool | None = None


class DatasetRead(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None
    metric_type: str
    unit: str
    currency: str
    granularity: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_import_at: datetime | None = None
    point_count: int = 0
    last_point_at: datetime | None = None


class PointCreate(BaseModel):
    timestamp: datetime
    value: float = Field(gt=-1e15, lt=1e15)
    meta: dict[str, Any] | None = None


class PointsBulkCreate(BaseModel):
    points: list[PointCreate] = Field(min_length=1, max_length=5000)


class BulkResult(BaseModel):
    dataset_id: int
    inserted: int
    skipped_duplicates: int
    total: int


class PointRead(ORMModel):
    id: int
    timestamp: datetime
    value: float
    meta: dict[str, Any] | None
