"""Forecasting schemas."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ForecastPoint(BaseModel):
    timestamp: datetime
    value: float
    lower: float | None = None
    upper: float | None = None


class ForecastMetrics(BaseModel):
    method: str
    mape: float | None = None
    mae: float | None = None
    rmse: float | None = None
    holdout_points: int = 0


class ForecastResponse(BaseModel):
    dataset_id: int
    horizon: int
    method: str
    seasonality: bool = False
    metrics: ForecastMetrics
    points: list[ForecastPoint]
