"""Analytics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel

from app.schemas.dataset import DatasetRead


class Kpi(BaseModel):
    key: str
    label: str
    value: float
    unit: str = ""
    change_pct: float | None = None
    metadata: dict[str, Any] | None = None


class SeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class Trend(BaseModel):
    slope: float
    intercept: float
    r_squared: float
    direction: str
    fitted: list[SeriesPoint]


class AnalyticsResponse(BaseModel):
    dataset: DatasetRead
    kpis: list[Kpi]
    series: list[SeriesPoint]
    trend: Trend
    period: dict[str, datetime] | None = None
