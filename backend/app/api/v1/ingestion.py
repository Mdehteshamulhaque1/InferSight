"""File ingestion API routes: preview and import CSV/XLSX/JSON uploads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from app.api.deps import CurrentUser, DbSession, user_rate_limit
from app.models.dataset import utcnow
from app.services import audit_service, dataset_service, ingestion_service
from app.services.dataset_service import (
    DatasetAccessError,
    DatasetNotFoundError,
    SlugConflictError,
)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

_GENERIC_STEMS = {
    "data",
    "dataset",
    "export",
    "exported",
    "upload",
    "uploaded",
    "file",
    "csv",
    "sheet",
    "untitled",
    "new",
    "sample",
}

_METRIC_KEYWORDS = {
    "revenue": ("revenue", "sales", "gmv", "income", "amount", "turnover", "earning"),
    "traffic": ("traffic", "session", "pageview", "view", "impression", "click", "visit"),
    "users": ("user", "visitor", "active", "customer", "signup", "registration", "member"),
    "transactions": ("transaction", "order", "purchase", "checkout", "conversion"),
}


def _infer_currency(raw: bytes) -> str:
    head = raw[:4096].decode("utf-8-sig", errors="ignore").lower()
    if "€" in head or "eur" in head:
        return "EUR"
    if "£" in head or "gbp" in head:
        return "GBP"
    return "USD"


def _infer_metric_type(filename: str, value_column: str) -> str:
    haystack = f"{filename} {value_column}".lower()
    for metric, keywords in _METRIC_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            return metric
    return "custom"


def _infer_name(filename: str, value_column: str) -> str:
    stem = filename.rsplit(".", 1)[0].strip().replace("_", " ").replace("-", " ")
    words = [
        w
        for w in stem.split()
        if w.lower() not in _GENERIC_STEMS and not w.replace(".", "").isdigit()
    ]
    if words:
        return " ".join(w[:1].upper() + w[1:] for w in words)
    return f"{value_column.strip().title()} dataset"


def _infer_attrs(
    filename: str, raw: bytes, parsed: dict
) -> dict:
    return {
        "name": _infer_name(filename, parsed["value_column"]),
        "metric_type": _infer_metric_type(filename, parsed["value_column"]),
        "unit": parsed["value_column"].strip().lower() or None,
        "currency": _infer_currency(raw),
        "granularity": parsed["granularity"],
    }


def _load_dataset(db: DbSession, dataset_id: int, user) -> object:
    try:
        return dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def _ingest_parsed(
    db: DbSession, dataset, user, parsed: dict, filename: str, replace: bool
) -> dict:
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
    dataset.last_import_at = utcnow()
    audit_service.create_version(
        db, dataset, user, "file.ingest", inserted, skipped, filename=filename
    )
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
    from app.services.cache import cache_service

    cache_service.invalidate_prefix("sum")
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


def _run_ingest(
    db: DbSession, dataset, user, filename: str, raw: bytes, replace: bool
) -> dict:
    parsed = ingestion_service.parse_upload(filename, raw)
    return _ingest_parsed(db, dataset, user, parsed, filename, replace)


@router.post("/preview", summary="Preview a file before importing (no dataset required)")
def preview_file(
    request: Request,
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    _: Annotated[None, Depends(user_rate_limit(max_requests=30, window_seconds=300))],
) -> dict:
    filename = file.filename or "upload.csv"
    raw = file.file.read()
    try:
        parsed = ingestion_service.parse_upload(filename, raw)
    except ingestion_service.IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return {
        "filename": filename,
        "columns": parsed["columns"],
        "timestamp_column": parsed["timestamp_column"],
        "value_column": parsed["value_column"],
        "detected_granularity": parsed["granularity"],
        "parsed_points": parsed["point_count"],
        "dropped": parsed["dropped"],
        "sample": parsed["points"][:10],
    }


@router.post(
    "/auto",
    status_code=status.HTTP_201_CREATED,
    summary="Auto-create a dataset from a file and ingest it",
)
def auto_import(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[None, Depends(user_rate_limit(max_requests=30, window_seconds=300))],
    file: Annotated[UploadFile, File()],
) -> dict:
    """Upload-first onboarding: no dataset exists yet. Attributes (name, metric,
    unit, currency, granularity) are inferred from the file itself."""
    filename = file.filename or "upload.csv"
    raw = file.file.read()
    try:
        parsed = ingestion_service.parse_upload(filename, raw)
    except ingestion_service.IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    from app.schemas.dataset import DatasetCreate

    attrs = _infer_attrs(filename, raw, parsed)
    payload = DatasetCreate(**attrs)
    try:
        dataset = dataset_service.create_dataset(db, user, payload)
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DatasetAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    result = _ingest_parsed(db, dataset, user, parsed, filename, replace=False)
    from app.api.v1.datasets import _dataset_read

    return {"dataset": _dataset_read(db, dataset), "result": result}


@router.post("/{dataset_id}/preview", summary="Preview a file before importing")
def preview_ingest(
    dataset_id: int,
    request: Request,
    file: Annotated[UploadFile, File()],
    db: DbSession,
    user: CurrentUser,
    _: Annotated[None, Depends(user_rate_limit(max_requests=30, window_seconds=300))],
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
    _: Annotated[None, Depends(user_rate_limit(max_requests=30, window_seconds=300))],
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
