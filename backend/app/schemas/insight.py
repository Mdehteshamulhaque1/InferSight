"""Insight schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel

from app.schemas.common import ORMModel


class InsightOut(ORMModel):
    id: int
    dataset_id: int | None
    kind: str
    severity: str
    title: str
    body: str
    payload: dict[str, Any] | None
    created_at: datetime


class InsightCreate(BaseModel):
    dataset_id: int | None = None
    kind: str = "insight"
    severity: str = "info"
    title: str
    body: str
    payload: dict[str, Any] | None = None
