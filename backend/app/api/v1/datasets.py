"""Dataset and metric-point API routes."""

from __future__ import annotations

from typing import Annotated

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message, Paginated
from app.schemas.dataset import (
    BulkResult,
    DatasetCreate,
    DatasetRead,
    DatasetUpdate,
    PointCreate,
    PointsBulkCreate,
    PointRead,
)
from app.services import dataset_service
from app.services.audit_service import create_version, record_event
from app.services.cache import cache_service
from app.services.dataset_service import (
    DatasetAccessError,
    DatasetNotFoundError,
    SlugConflictError,
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


def _dataset_read(db: DbSession, dataset) -> DatasetRead:
    count, last_ts = dataset_service.get_points_bounds(db, dataset)
    return DatasetRead(
        **{
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
    )


@router.get("", response_model=Paginated[DatasetRead], summary="List my datasets")
def list_datasets(
    db: DbSession,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = dataset_service.list_datasets(db, user, page, limit)
    return {
        "items": [_dataset_read(db, d) for d in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@router.post(
    "",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a dataset",
)
def create_dataset(payload: DatasetCreate, db: DbSession, user: CurrentUser) -> DatasetRead:
    try:
        dataset = dataset_service.create_dataset(db, user, payload)
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    record_event(db, user, "dataset.create", "dataset", dataset.id)
    db.commit()
    cache_service.invalidate_prefix(f"ds:{dataset.id}")
    return _dataset_read(db, dataset)


@router.get("/{dataset_id}", response_model=DatasetRead, summary="Get a dataset")
def get_dataset(dataset_id: int, db: DbSession, user: CurrentUser) -> DatasetRead:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _dataset_read(db, dataset)


@router.patch("/{dataset_id}", response_model=DatasetRead, summary="Update a dataset")
def update_dataset(
    dataset_id: int, payload: DatasetUpdate, db: DbSession, user: CurrentUser
) -> DatasetRead:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
        dataset_service.require_write_access(db, dataset, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        dataset = dataset_service.update_dataset(db, dataset, payload)
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_event(db, user, "dataset.update", "dataset", dataset.id)
    db.commit()
    cache_service.invalidate_prefix(f"ds:{dataset.id}")
    return _dataset_read(db, dataset)


@router.delete("/{dataset_id}", response_model=Message, summary="Delete a dataset")
def delete_dataset(dataset_id: int, db: DbSession, user: CurrentUser) -> Message:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
        dataset_service.require_write_access(db, dataset, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    cache_service.invalidate_prefix(f"ds:{dataset.id}")
    dataset_service.delete_dataset(db, dataset)
    record_event(db, user, "dataset.delete", "dataset", dataset.id)
    db.commit()
    return Message(detail="dataset deleted")


@router.get(
    "/{dataset_id}/points",
    response_model=Paginated[PointRead],
    summary="List metric points",
)
def list_points(
    dataset_id: int,
    db: DbSession,
    user: CurrentUser,
    start: datetime | None = None,
    end: datetime | None = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> dict:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    points = dataset_service.get_points(
        db, dataset, start=start, end=end, limit=limit, order=order
    )
    total = dataset_service.count_points(db, dataset, start=start, end=end)
    return {
        "items": [PointRead.model_validate(p) for p in points],
        "total": total,
        "page": 1,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@router.post(
    "/{dataset_id}/points",
    response_model=BulkResult,
    summary="Ingest metric points (idempotent)",
)
def ingest_points(
    dataset_id: int, payload: PointsBulkCreate, db: DbSession, user: CurrentUser
) -> BulkResult:
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
        dataset_service.require_write_access(db, dataset, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    inserted, skipped = dataset_service.ingest_points(db, dataset, payload.points)
    if inserted:
        create_version(db, dataset, user, "points.bulk", inserted, skipped)
        record_event(
            db,
            user,
            "points.ingest",
            "dataset",
            dataset.id,
            {"inserted": inserted, "skipped": skipped},
        )
        db.commit()
    cache_service.invalidate_prefix(f"ds:{dataset.id}")
    return BulkResult(
        dataset_id=dataset.id,
        inserted=inserted,
        skipped_duplicates=skipped,
        total=len(payload.points),
    )
