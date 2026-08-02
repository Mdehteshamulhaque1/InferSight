"""Dataset versioning and audit-trail services.

Every mutation that touches a dataset's points or metadata is recorded as an
append-only AuditEvent. Point mutations additionally write an immutable
DatasetVersion whose `snapshot` is the full {iso_timestamp: value} mapping,
enabling rollback to any prior state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, MetricPoint
from app.models.user import User
from app.models.versioning import AuditEvent, DatasetVersion


def _iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


def snapshot_points(db: Session, dataset: Dataset) -> dict[str, float]:
    rows = db.execute(
        select(MetricPoint.timestamp, MetricPoint.value).where(
            MetricPoint.dataset_id == dataset.id
        )
    ).all()
    return {_iso(ts): value for ts, value in rows}


def record_event(
    db: Session,
    user: User | None,
    action: str,
    resource_type: str = "dataset",
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    db.flush()
    return event


def create_version(
    db: Session,
    dataset: Dataset,
    user: User,
    source: str,
    points_added: int,
    points_removed: int,
    filename: str | None = None,
    status: str = "success",
) -> DatasetVersion:
    latest = db.scalar(
        select(func.max(DatasetVersion.version_no)).where(
            DatasetVersion.dataset_id == dataset.id
        )
    )
    total = db.scalar(
        select(func.count()).select_from(MetricPoint).where(
            MetricPoint.dataset_id == dataset.id
        )
    )
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_no=(latest or 0) + 1,
        user_id=user.id,
        source=source,
        points_added=points_added,
        points_removed=points_removed,
        total_after=total,
        filename=filename,
        status=status,
        snapshot=snapshot_points(db, dataset),
    )
    db.add(version)
    db.flush()
    return version


def list_versions(db: Session, dataset: Dataset) -> list[DatasetVersion]:
    return list(
        db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset.id)
            .order_by(DatasetVersion.version_no.desc())
        ).all()
    )


def get_version(db: Session, dataset: Dataset, version_no: int) -> DatasetVersion | None:
    return db.scalar(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.version_no == version_no,
        )
    )


def rollback_to_version(db: Session, dataset: Dataset, version: DatasetVersion) -> int:
    """Restore the dataset's points to the state captured by `version`.

    Returns the number of points after restore. Deletes all current points and
    bulk-inserts the snapshot — one transaction, atomic by construction.
    """
    db.query(MetricPoint).filter(MetricPoint.dataset_id == dataset.id).delete(
        synchronize_session=False
    )
    restored = 0
    for iso_ts, value in version.snapshot.items():
        db.add(
            MetricPoint(
                dataset_id=dataset.id,
                timestamp=datetime.fromisoformat(iso_ts),
                value=float(value),
            )
        )
        restored += 1
    db.flush()
    return restored


def list_events(
    db: Session,
    user: User,
    limit: int = 100,
    resource_id: int | None = None,
) -> list[AuditEvent]:
    query = select(AuditEvent).where(AuditEvent.user_id == user.id)
    if resource_id is not None:
        query = query.where(AuditEvent.resource_id == resource_id)
    return list(
        db.scalars(query.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    )
