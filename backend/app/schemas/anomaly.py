"""Anomaly detection schemas."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class Anomaly(BaseModel):
    dataset_id: int | None = None
    timestamp: datetime
    value: float
    expected: float
    score: float
    severity: str
    direction: str
    reason: str


class AnomalyResponse(BaseModel):
    dataset_id: int
    method: str
    window: int
    threshold: float
    total_points: int
    anomalies: list[Anomaly]
    summary: dict[str, int]
