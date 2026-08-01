"""Intelligence schemas: profiling, KPI discovery, root-cause, recommendations,
health score, chat, alerts, versions, and audit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ProfileOut(BaseModel):
    count: int
    start: datetime | None
    end: datetime | None
    span_days: float
    stats: dict[str, float]
    trend: dict[str, Any]
    seasonality: dict[str, Any]
    quality: dict[str, Any]
    top_points: list[dict[str, Any]]
    bottom_points: list[dict[str, Any]]
    biggest_movers: list[dict[str, Any]]


class SegmentContribution(BaseModel):
    dimension: str
    segment: str
    value: float
    baseline: float
    change_pct: float
    weight: float


class TimeEffect(BaseModel):
    factor: str
    value: str
    relative_change_pct: float
    points: int


class Hypothesis(BaseModel):
    title: str
    evidence: str
    confidence: str


class RootCauseOut(BaseModel):
    timestamp: datetime
    actual: float
    expected: float
    delta: float
    delta_pct: float
    direction: str
    contributing_segments: list[SegmentContribution]
    time_effects: list[TimeEffect]
    hypotheses: list[Hypothesis]
    related_signals: list["RelatedSignalOut"] = []


class RelatedSignalOut(BaseModel):
    """A same-organization dataset whose series moved with an anomaly."""

    dataset_id: int
    dataset_name: str
    correlation: float
    direction: str


class RecommendationOut(BaseModel):
    id: str
    severity: str
    category: str
    action: str
    rationale: str
    impact: str


class HealthComponent(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    detail: str


class HealthScoreOut(BaseModel):
    score: int
    grade: str
    verdict: str
    components: list[HealthComponent]


class ChatOut(BaseModel):
    intent: str
    reply: str
    data: dict[str, Any] | None = None
    followups: list[str]


class AlertOut(ORMModel):
    id: int
    dataset_id: int | None
    kind: str
    severity: str
    title: str
    body: str
    is_read: bool
    created_at: datetime


class DatasetVersionOut(ORMModel):
    id: int
    dataset_id: int
    version_no: int
    user_id: int
    source: str
    points_added: int
    points_removed: int
    total_after: int
    created_at: datetime


class AuditEventOut(ORMModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    details: dict[str, Any] | None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
    dataset_id: int | None = None


class RootCauseRequest(BaseModel):
    dataset_id: int
    timestamp: datetime | None = None
