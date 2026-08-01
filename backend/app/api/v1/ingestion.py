"""File ingestion API routes: preview and import CSV/XLSX/JSON uploads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.services import audit_service, dataset_service, ingestion_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


def _load_dataset(db: DbSession, dataset_id: int, user) -> object:
    try:
        return dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def _run_ingest(
    db: DbSession, dataset, user, filename: str, raw: bytes, replace: bool
) -> dict:
    parsed = ingestion_service.parse_upload(filename, raw)
    points = [
        {
            "timestamp": p["timestamp"],
            "value": p["value"],
            "meta": p.get("meta"),
        }
        for p in parsed["points"]
    ]
    from app.schemas.dataset import PointCreate

    payload = [PointCreate.model_validate(p) for p in points]
    if replace:
        dataset_service.clear_points(db, dataset)
        removed_meta = {"replaced": True}
    else:
        removed_meta = {}
    inserted, skipped = dataset_service.ingest_points(db, dataset, payload)
    audit_service.create_version(db, dataset, user, "file.ingest", inserted, skipped)
    audit_service.record_event(
        db,
        user,
        "points.ingest.file",
        "dataset",
        dataset.id,
        {"filename": filename, "inserted": inserted, "skipped": skipped, **removed_meta},
    )
    db.commit()
    dataset_service.update_granularity_if_detected(db, dataset, parsed["granularity"])
    return {
        "dataset_id": dataset.id,
        "filename": filename,
        "columns": parsed["columns"],
        "timestamp_column": parsed["timestamp_column"],
        "value_column": parsed["value_column"],
        "detected_granularity": parsed["granularity"],
        "parsed_points": parsed["point_count"],
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "dropped": parsed["dropped"],
        "replaced": replace,
        "point_count": dataset_service.count_points(db, dataset),
    }


@router.post("/{dataset_id}/preview", summary="Preview a file before importing")
def preview_ingest(
    dataset_id: int,
    request: Request,
    file: Annotated[UploadFile, File()],
    db: DbSession,
    user: CurrentUser,
) -> dict:
    dataset = _load_dataset(db, dataset_id, user)
    raw = file.file.read()
    parsed = ingestion_service.parse_upload(file.filename or "upload.csv", raw)
    return {
        "dataset_id": dataset.id,
        "filename": file.filename,
        "columns": parsed["columns"],
        "timestamp_column": parsed["timestamp_column"],
        "value_column": parsed["value_column"],
        "detected_granularity": parsed["granularity"],
        "parsed_points": parsed["point_count"],
        "dropped": parsed["dropped"],
        "sample": parsed["points"][:10],
    }


@router.post(
    "/{dataset_id}/file",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a CSV/XLSX/JSON file",
)
def ingest_file(
    dataset_id: int,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    replace: Annotated[bool, Query(description="replace existing points")] = False,
) -> dict:
    dataset = _load_dataset(db, dataset_id, user)
    dataset_service.require_write_access(db, dataset, user)
    raw = file.file.read()
    try:
        return _run_ingest(db, dataset, user, file.filename or "upload.csv", raw, replace)
    except ingestion_service.IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
