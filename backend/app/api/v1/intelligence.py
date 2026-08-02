"""Intelligence API routes: profiling, KPI discovery, root-cause, related
signals, recommendations, health score, chat, and dataset versioning."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, user_rate_limit
from app.schemas.common import Message, Paginated
from app.schemas.intelligence import (
    ChatOut,
    ChatRequest,
    DatasetVersionOut,
    HealthScoreOut,
    ProfileOut,
    RecommendationOut,
    RelatedSignalOut,
    RootCauseOut,
)
from app.services import (
    analytics_service,
    audit_service,
    dataset_service,
    forecast_service,
    intelligence_service,
)
from app.services.anomaly_service import detect as detect_anomalies
from app.services.cache import cache_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(tags=["Intelligence"])

INTELLIGENCE = APIRouter(prefix="/datasets", tags=["Intelligence"])


def _load_dataset(db: DbSession, dataset_id: int, user) -> object:
    try:
        return dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _load_points(db: DbSession, dataset):
    points = dataset_service.get_points(db, dataset, limit=20000)
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points to analyze",
        )
    return points


# --------------------------------------------------------------------------- #
# Profiling & KPI discovery
# --------------------------------------------------------------------------- #
@INTELLIGENCE.get(
    "/{dataset_id}/profile",
    response_model=ProfileOut,
    summary="Statistical profile of a dataset",
)
def dataset_profile(
    dataset_id: int, db: DbSession, user: CurrentUser
) -> ProfileOut:
    dataset = _load_dataset(db, dataset_id, user)
    points = dataset_service.get_points(db, dataset, limit=20000)
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points to profile",
        )
    return ProfileOut.model_validate(
        intelligence_service.profile(points, dataset.granularity)
    )


@INTELLIGENCE.get("/{dataset_id}/kpis/discover", summary="Discover ranked KPIs")
def discover_kpis(dataset_id: int, db: DbSession, user: CurrentUser) -> list[dict]:
    dataset = _load_dataset(db, dataset_id, user)
    points = dataset_service.get_points(db, dataset, limit=20000)
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points",
        )
    return intelligence_service.discover_kpis(points, dataset.granularity, dataset.unit)


# --------------------------------------------------------------------------- #
# Root-cause, recommendations, health, chat
# --------------------------------------------------------------------------- #
@INTELLIGENCE.get(
    "/{dataset_id}/root-cause",
    response_model=RootCauseOut,
    summary="Root-cause analysis for the most severe anomaly",
)
def root_cause(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    timestamp: str | None = None,
) -> RootCauseOut:
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    if len(points) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="at least 6 data points are required for root-cause analysis",
        )
    response = detect_anomalies(points, window=7, threshold=3.0)
    target = None
    if timestamp is not None:
        from datetime import datetime

        try:
            ts = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="timestamp must be ISO-8601",
            ) from exc
        for anomaly in response.anomalies:
            if anomaly.timestamp.date() == ts.date():
                target = anomaly
                break
    if target is None and response.anomalies:
        target = max(response.anomalies, key=lambda a: abs(a.score))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="no anomalies found to root-cause",
        )
    return RootCauseOut.model_validate(
        intelligence_service.root_cause(points, target, dataset.granularity, db_session=db)
    )


@INTELLIGENCE.get(
    "/{dataset_id}/anomalies/{anomaly_id}/related",
    response_model=list[RelatedSignalOut],
    summary="Datasets in the organization correlated with a specific anomaly",
)
def related_signals(
    dataset_id: int,
    anomaly_id: int,
    db: DbSession,
    user: CurrentUser,
) -> list[dict]:
    """Return the related_signals list for one anomaly of a dataset.

    ``anomaly_id`` is the zero-based index of the anomaly within the dataset's
    detection result (``GET /anomalies/datasets/{dataset_id}``). The result is
    cached for ten minutes keyed on the anomaly.
    """
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    if len(points) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="at least 6 data points are required for anomaly correlation",
        )
    response = detect_anomalies(points, window=7, threshold=3.0)
    if anomaly_id < 0 or anomaly_id >= len(response.anomalies):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no anomaly found at that index",
        )
    anomaly = response.anomalies[anomaly_id]

    cached = cache_service.cache_get_json("rel", dataset_id, anomaly_id, user.id)
    if cached is not None:
        return cached

    signals = analytics_service.find_related_datasets(anomaly, db)
    cache_service.cache_set_json(
        signals, "rel", dataset_id, anomaly_id, user.id, ttl=600
    )
    return signals


@INTELLIGENCE.get(
    "/{dataset_id}/recommendations",
    response_model=list[RecommendationOut],
    summary="Prioritized action recommendations",
)
def recommendations(dataset_id: int, db: DbSession, user: CurrentUser) -> list[dict]:
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    if len(points) < 6:
        return []
    response = detect_anomalies(points, window=7, threshold=3.0)
    return intelligence_service.recommend(
        points, anomalies=response.anomalies, granularity=dataset.granularity
    )


@INTELLIGENCE.get(
    "/{dataset_id}/health",
    response_model=HealthScoreOut,
    summary="Business health score",
)
def dataset_health(dataset_id: int, db: DbSession, user: CurrentUser) -> HealthScoreOut:
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    response = detect_anomalies(points, window=7, threshold=3.0)
    return HealthScoreOut.model_validate(
        intelligence_service.health_score(
            points, anomalies=response.anomalies, granularity=dataset.granularity
        )
    )


@INTELLIGENCE.get(
    "/{dataset_id}/summary",
    summary="Composite analysis summary (KPIs, anomalies, forecast, health) for the Copilot",
)
def dataset_summary(dataset_id: int, db: DbSession, user: CurrentUser) -> dict:
    """One-call composite analysis: KPIs, trend, anomalies, forecast, and health
    score. Powers the Copilot's analysis-complete checklist and guided report."""
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    if len(points) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="at least 3 data points are required for analysis",
        )
    cached = cache_service.cache_get_json("sum", dataset_id, user.id)
    if cached is not None:
        return cached

    series = analytics_service.resample(points, dataset.granularity)
    kpis = analytics_service.compute_kpis(series)
    trend = analytics_service.linear_trend(points)
    response = detect_anomalies(points, window=7, threshold=3.0)

    mean = sum(p.value for p in points) / len(points)
    slope_pct = (trend.slope / mean * 100.0) if mean else 0.0

    forecast_data = None
    try:
        fc = forecast_service.forecast(
            points, horizon=30, method="auto", granularity=dataset.granularity
        )
        forecast_data = {
            "method": fc.method,
            "horizon": fc.horizon,
            "seasonality": fc.seasonality,
            "mape": fc.metrics.mape,
            "points": [p.model_dump() for p in fc.points],
        }
    except Exception:
        forecast_data = None

    health = intelligence_service.health_score(
        points, anomalies=response.anomalies, granularity=dataset.granularity
    )

    payload = {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "currency": dataset.currency,
        "granularity": dataset.granularity,
        "kpis": [k.model_dump() for k in kpis],
        "trend": {
            "direction": trend.direction,
            "slope_per_period_pct": round(slope_pct, 2),
            "r_squared": trend.r_squared,
        },
        "anomaly_count": len(response.anomalies),
        "critical_anomalies": response.summary.get("critical", 0),
        "forecast": forecast_data,
        "health": {
            "score": health["score"],
            "grade": health["grade"],
            "verdict": health["verdict"],
        },
    }
    cache_service.cache_set_json(payload, "sum", dataset_id, user.id, ttl=120)
    return payload


@router.post("/chat", response_model=ChatOut, summary="Ask about your data in plain language")
def chat(
    payload: ChatRequest,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[None, Depends(user_rate_limit(max_requests=30, window_seconds=60))],
) -> ChatOut:
    if not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="message is required"
        )
    if payload.dataset_id is None:
        items, _ = dataset_service.list_datasets(db, user, 1, 1)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="create a dataset first",
            )
        dataset = items[0]
    else:
        dataset = _load_dataset(db, payload.dataset_id, user)
    points = _load_points(db, dataset)
    response = detect_anomalies(points, window=7, threshold=3.0)
    return ChatOut.model_validate(
        intelligence_service.chat(
            payload.message,
            points,
            dataset,
            anomalies=response.anomalies,
            granularity=dataset.granularity,
        )
    )


# --------------------------------------------------------------------------- #
# Versioning
# --------------------------------------------------------------------------- #
@INTELLIGENCE.get(
    "/{dataset_id}/versions",
    response_model=Paginated[DatasetVersionOut],
    summary="Dataset version history",
)
def list_versions(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    dataset = _load_dataset(db, dataset_id, user)
    versions = audit_service.list_versions(db, dataset)
    offset = (page - 1) * limit
    items = versions[offset : offset + limit]
    total = len(versions)
    return {
        "items": [DatasetVersionOut.model_validate(v) for v in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@INTELLIGENCE.post(
    "/{dataset_id}/versions/{version_no}/rollback",
    response_model=Message,
    summary="Roll the dataset back to an earlier version",
)
def rollback(
    dataset_id: int,
    version_no: int,
    db: DbSession,
    user: CurrentUser,
) -> Message:
    dataset = _load_dataset(db, dataset_id, user)
    dataset_service.require_write_access(db, dataset, user)
    version = audit_service.get_version(db, dataset, version_no)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="version not found"
        )
    restored = audit_service.rollback_to_version(db, dataset, version)
    audit_service.create_version(db, dataset, user, "rollback", 0, 0)
    audit_service.record_event(
        db,
        user,
        "dataset.rollback",
        "dataset",
        dataset.id,
        {"to_version": version_no, "restored": restored},
    )
    db.commit()
    return Message(detail=f"restored to version {version_no} ({restored} points)")


router.include_router(INTELLIGENCE)
