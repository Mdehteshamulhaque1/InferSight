"""Alert API routes: list, unread count, sync, and read state."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message, Paginated
from app.schemas.intelligence import AlertOut
from app.services import alert_service, dataset_service
from app.services.anomaly_service import detect as detect_anomalies
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/alerts", tags=["Alerts"])


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


@router.get("", response_model=Paginated[AlertOut], summary="List alerts")
def list_alerts(
    db: DbSession,
    user: CurrentUser,
    unread_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    all_alerts = alert_service.list_alerts(db, user, unread_only=unread_only, limit=limit)
    offset = (page - 1) * limit
    items = all_alerts[offset : offset + limit]
    total = len(all_alerts)
    return {
        "items": [AlertOut.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@router.get("/unread-count", summary="Unread alert count")
def unread_count(db: DbSession, user: CurrentUser) -> dict:
    return {"count": alert_service.unread_count(db, user)}


@router.post(
    "/sync/{dataset_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Detect anomalies and persist alerts",
)
def sync_alerts(dataset_id: int, db: DbSession, user: CurrentUser) -> dict:
    dataset = _load_dataset(db, dataset_id, user)
    points = _load_points(db, dataset)
    if len(points) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="at least 6 data points are required",
        )
    response = detect_anomalies(points, window=7, threshold=3.0)
    created = alert_service.sync_alerts_from_anomalies(
        db, user, dataset.id, response.anomalies
    )
    return {
        "dataset_id": dataset.id,
        "anomalies": len(response.anomalies),
        "critical": response.summary.get("critical", 0),
        "alerts_created": created,
    }


@router.post("/{alert_id}/read", response_model=AlertOut, summary="Mark an alert read")
def mark_read(alert_id: int, db: DbSession, user: CurrentUser) -> AlertOut:
    try:
        alert = alert_service.mark_read(db, user, alert_id)
    except alert_service.AlertNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except alert_service.AlertAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AlertOut.model_validate(alert)


@router.post("/read-all", response_model=Message, summary="Mark all alerts read")
def mark_all_read(db: DbSession, user: CurrentUser) -> Message:
    cleared = alert_service.mark_all_read(db, user)
    return Message(detail=f"{cleared} alerts marked read")
