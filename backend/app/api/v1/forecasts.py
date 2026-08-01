"""Forecasting API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.forecast import ForecastResponse
from app.services import dataset_service, forecast_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError
from app.services.forecast_service import ForecastError

router = APIRouter(prefix="/forecasts", tags=["Forecasting"])


@router.get("/datasets/{dataset_id}", response_model=ForecastResponse, summary="Forecast a dataset into the future")
def forecast_dataset(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    horizon: Annotated[int, Query(ge=1, le=365)] = 30,
    method: Annotated[str, Query(pattern="^(auto|linear|es|holt)$")] = "auto",
    max_points: Annotated[int, Query(ge=3, le=20000)] = 5000,
) -> ForecastResponse:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    points = dataset_service.get_points(db, dataset, limit=max_points)
    try:
        return forecast_service.forecast(
            points,
            horizon=horizon,
            method=method,
            granularity=dataset.granularity,
        )
    except ForecastError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
