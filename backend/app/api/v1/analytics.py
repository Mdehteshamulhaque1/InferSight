"""Analytics API routes."""

from __future__ import annotations

from typing import Annotated

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.analytics import AnalyticsResponse
from app.services import analytics_service, dataset_service
from app.services.cache import cache_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/datasets/{dataset_id}", response_model=AnalyticsResponse, summary="Full analytics for a dataset")
def dataset_analytics(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    start: datetime | None = None,
    end: datetime | None = None,
    granularity: str | None = Query(default=None, pattern="^(hour|day|week|month)$"),
    max_points: Annotated[int, Query(ge=10, le=20000)] = 5000,
) -> AnalyticsResponse:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    cache_key = f"analytics:{dataset.id}"
    cached = cache_service.cache_get_json(
        "an", cache_key, start, end, granularity, max_points, user.id
    )
    if cached is not None:
        return AnalyticsResponse.model_validate(cached)

    points = dataset_service.get_points(
        db, dataset, start=start, end=end, limit=max_points
    )
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points in the requested range",
        )

    eff_granularity = granularity or dataset.granularity
    series = analytics_service.resample(points, eff_granularity)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="no data to aggregate",
        )
    kpis = analytics_service.compute_kpis(series)
    trend = analytics_service.linear_trend(points)

    response = AnalyticsResponse(
        dataset=_dataset_read(dataset, len(points), points[-1].timestamp),
        kpis=kpis,
        series=series,
        trend=trend,
        period={"start": points[0].timestamp, "end": points[-1].timestamp},
    )
    cache_service.cache_set_json(response.model_dump(mode="json"), "an", cache_key, start, end, granularity, max_points, user.id)
    return response


@router.get("/datasets/{dataset_id}/kpis", summary="KPI cards for a dataset")
def dataset_kpis(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    granularity: str | None = Query(default=None, pattern="^(hour|day|week|month)$"),
) -> list[dict]:
    analytics = dataset_analytics(dataset_id, db, user, granularity=granularity)
    return [kpi.model_dump(mode="json") for kpi in analytics.kpis]


@router.get("/datasets/{dataset_id}/series", summary="Resampled time series for a dataset")
def dataset_series(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    granularity: str | None = Query(default=None, pattern="^(hour|day|week|month)$"),
    max_points: Annotated[int, Query(ge=10, le=20000)] = 5000,
) -> list[dict]:
    analytics = dataset_analytics(
        dataset_id, db, user, granularity=granularity, max_points=max_points
    )
    return [point.model_dump(mode="json") for point in analytics.series]


@router.get("/datasets/{dataset_id}/trend", summary="Linear trend fit for a dataset")
def dataset_trend(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    analytics = dataset_analytics(dataset_id, db, user)
    return analytics.trend.model_dump(mode="json")


def _dataset_read(dataset, count: int, last_ts: datetime | None) -> dict:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "slug": dataset.slug,
        "description": dataset.description,
        "metric_type": dataset.metric_type,
        "unit": dataset.unit,
        "currency": dataset.currency,
        "granularity": dataset.granularity,
        "is_active": dataset.is_active,
        "created_at": dataset.created_at,
        "updated_at": dataset.updated_at,
        "point_count": count,
        "last_point_at": last_ts,
    }
