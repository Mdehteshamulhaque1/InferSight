"""Insight generation API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message, Paginated
from app.schemas.insight import InsightOut
from app.services import analytics_service, dataset_service, insight_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.post(
    "/datasets/{dataset_id}",
    response_model=InsightOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and persist an AI insight for a dataset",
)
def generate_insight(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    enrich_with_llm: Annotated[bool, Query()] = True,
) -> InsightOut:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    points = dataset_service.get_points(db, dataset, limit=5000)
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points to analyze",
        )
    series = analytics_service.resample(points, dataset.granularity)
    kpis = analytics_service.compute_kpis(series)
    trend = analytics_service.linear_trend(points)

    insight = insight_service.generate_dataset_insight(
        db, user, dataset, points, kpis, trend
    )
    return InsightOut.model_validate(insight)


@router.get("", response_model=Paginated[InsightOut], summary="List generated insights")
def list_insights(
    db: DbSession,
    user: CurrentUser,
    dataset_id: int | None = None,
    kind: Annotated[str | None, Query(pattern="^(insight|anomaly|forecast)$")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = insight_service.list_insights(
        db, user, dataset_id=dataset_id, kind=kind, page=page, limit=limit
    )
    return {
        "items": [InsightOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@router.delete("/{insight_id}", response_model=Message, summary="Delete an insight")
def delete_insight(insight_id: int, db: DbSession, user: CurrentUser) -> Message:
    try:
        insight_service.delete_insight(db, insight_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Message(detail="insight deleted")
