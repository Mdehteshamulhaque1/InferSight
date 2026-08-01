"""Anomaly detection API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.anomaly import AnomalyResponse
from app.services import anomaly_service, dataset_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("/datasets/{dataset_id}", response_model=AnomalyResponse, summary="Detect anomalies in a dataset")
def detect_anomalies(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    window: Annotated[int, Query(ge=2, le=90)] = 7,
    threshold: Annotated[float, Query(ge=1.0, le=10.0)] = 3.0,
    max_points: Annotated[int, Query(ge=10, le=20000)] = 5000,
) -> AnomalyResponse:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    points = dataset_service.get_points(db, dataset, limit=max_points)
    if len(points) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="at least 6 data points are required for anomaly detection",
        )
    return anomaly_service.detect(points, window=window, threshold=threshold)
