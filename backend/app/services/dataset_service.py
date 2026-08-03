"""Dataset persistence and metric-point ingestion services."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Dataset, MetricPoint, User
from app.schemas.dataset import DatasetCreate, DatasetUpdate, PointCreate
from app.services.rbac_service import can_read_dataset, can_write_dataset, dataset_read_scope
from app.utils.time import to_utc


class DatasetNotFoundError(Exception):
    pass


class SlugConflictError(Exception):
    pass


class DatasetAccessError(Exception):
    pass


def _slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9-_]+", "-", slug)
    slug = slug.strip("-")
    return slug or "dataset"


def _ensure_unique_slug(db: Session, owner_id: int, name: str) -> str:
    base = _slugify(name)
    slug = base
    counter = 1
    while db.scalar(select(Dataset).where(Dataset.owner_id == owner_id, Dataset.slug == slug)):
        counter += 1
        slug = f"{base}-{counter}"
    return slug


def list_datasets(db: Session, user: User, page: int, limit: int) -> tuple[list[Dataset], int]:
    base = select(Dataset).where(dataset_read_scope(db, user))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(Dataset.created_at.desc()).offset((page - 1) * limit).limit(limit)
    ).all()
    return list(items), total


def get_dataset(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFoundError("dataset not found")
    if not can_read_dataset(db, dataset, user):
        raise DatasetAccessError("you do not have access to this dataset")
    return dataset


def require_write_access(db: Session, dataset: Dataset, user: User) -> None:
    if not can_write_dataset(db, dataset, user):
        raise DatasetAccessError("write access denied")


def create_dataset(db: Session, user: User, payload: DatasetCreate) -> Dataset:
    slug = payload.slug or _ensure_unique_slug(db, user.id, payload.name)
    existing = db.scalar(
        select(Dataset).where(Dataset.owner_id == user.id, Dataset.slug == slug)
    )
    if existing is not None:
        raise SlugConflictError(f"a dataset with slug '{slug}' already exists")
    if payload.organization_id is not None:
        from app.models.organization import Organization
        from app.services.organization_service import (
            OrganizationAccessError,
            membership_for,
            require_role,
        )

        org = db.get(Organization, payload.organization_id)
        if org is None:
            raise DatasetAccessError("organization not found")
        try:
            member = membership_for(db, org, user)
            require_role(member, "manager")
        except OrganizationAccessError as exc:
            raise DatasetAccessError(str(exc)) from exc
    dataset = Dataset(
        owner_id=user.id,
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description,
        metric_type=payload.metric_type,
        unit=payload.unit,
        currency=payload.currency.upper(),
        granularity=payload.granularity,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def update_dataset(
    db: Session, dataset: Dataset, payload: DatasetUpdate
) -> Dataset:
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates and updates["slug"]:
        updates["slug"] = updates["slug"].strip().lower()
        existing = db.scalar(
            select(Dataset).where(
                Dataset.owner_id == dataset.owner_id,
                Dataset.slug == updates["slug"],
                Dataset.id != dataset.id,
            )
        )
        if existing is not None:
            raise SlugConflictError(f"a dataset with slug '{updates['slug']}' already exists")
    for field, value in updates.items():
        if field == "currency" and value:
            value = value.upper()
        setattr(dataset, field, value)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def delete_dataset(db: Session, dataset: Dataset) -> None:
    db.delete(dataset)
    db.commit()


def ingest_points(
    db: Session, dataset: Dataset, points: list[PointCreate]
) -> tuple[int, int]:
    """Insert points idempotently; duplicate (dataset, timestamp) pairs are skipped."""
    existing_ts = {
        to_utc(ts)
        for ts in db.scalars(
            select(MetricPoint.timestamp).where(MetricPoint.dataset_id == dataset.id)
        ).all()
    }
    inserted = 0
    skipped = 0
    for point in points:
        ts = to_utc(point.timestamp)
        if ts in existing_ts:
            skipped += 1
            continue
        db.add(
            MetricPoint(
                dataset_id=dataset.id,
                timestamp=ts,
                value=point.value,
                meta=point.meta,
            )
        )
        existing_ts.add(ts)
        inserted += 1
    db.commit()
    return inserted, skipped


def get_points(
    db: Session,
    dataset: Dataset,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 5000,
    order: str = "asc",
) -> list[MetricPoint]:
    stmt = select(MetricPoint).where(MetricPoint.dataset_id == dataset.id)
    if start is not None:
        stmt = stmt.where(MetricPoint.timestamp >= to_utc(start))
    if end is not None:
        stmt = stmt.where(MetricPoint.timestamp <= to_utc(end))
    if order == "desc":
        stmt = stmt.order_by(MetricPoint.timestamp.desc())
    else:
        stmt = stmt.order_by(MetricPoint.timestamp.asc())
    return list(db.scalars(stmt.limit(limit)).all())


def get_points_bounds(db: Session, dataset: Dataset) -> tuple[int, datetime | None]:
    row = db.execute(
        select(
            func.count(MetricPoint.id),
            func.max(MetricPoint.timestamp),
        ).where(MetricPoint.dataset_id == dataset.id)
    ).one()
    return row[0], row[1]


def count_points(
    db: Session,
    dataset: Dataset,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    stmt = select(func.count(MetricPoint.id)).where(MetricPoint.dataset_id == dataset.id)
    if start is not None:
        stmt = stmt.where(MetricPoint.timestamp >= to_utc(start))
    if end is not None:
        stmt = stmt.where(MetricPoint.timestamp <= to_utc(end))
    return db.scalar(stmt) or 0


def clear_points(db: Session, dataset: Dataset) -> int:
    """Remove all points (used by replace-on-ingest). Returns count removed."""
    removed = count_points(db, dataset)
    db.query(MetricPoint).filter(MetricPoint.dataset_id == dataset.id).delete(
        synchronize_session=False
    )
    db.flush()
    return removed


def update_granularity_if_detected(db: Session, dataset: Dataset, granularity: str) -> None:
    if dataset.granularity != granularity:
        dataset.granularity = granularity
        db.add(dataset)
        db.commit()
