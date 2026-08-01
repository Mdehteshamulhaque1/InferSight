"""Seed the database with a demo user and realistic time-series datasets.

Run from the backend directory:

    python -m scripts.seed

Creates:
  * demo@infersight.dev / demo12345  (analyst)
  * daily revenue dataset   (180 days, trend + weekly seasonality + anomalies)
  * daily transactions      (180 days, lighter)
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from app.database.session import SessionLocal, init_db
from app.models import Dataset, MetricPoint
from app.schemas.dataset import DatasetCreate, PointCreate
from app.services import auth_service, dataset_service

DEMO_EMAIL = "demo@infersight.dev"
DEMO_PASSWORD = "demo12345"


def _revenue_series(days: int = 180) -> list[tuple[datetime, float]]:
    rng = random.Random(42)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points: list[tuple[datetime, float]] = []
    for i in range(days):
        ts = base + timedelta(days=i)
        # Underlying growth trend + gentle noise.
        trend = 80_000 + i * 620
        noise = rng.gauss(0, 6_000)
        # Weekly seasonality: weekend uplift.
        weekday_factor = 1.12 if ts.weekday() >= 5 else 1.0
        # Synthetic anomalies.
        anomaly = 0.0
        if i == 61:
            anomaly = -28_000  # sudden drop
        elif i == 118:
            anomaly = +24_000  # traffic spike
        value = max(0.0, (trend + noise) * weekday_factor + anomaly)
        points.append((ts, round(value, 2)))
    return points


def _transactions_series(days: int = 120) -> list[tuple[datetime, float]]:
    rng = random.Random(7)
    base = datetime(2026, 2, 1, tzinfo=timezone.utc)
    points: list[tuple[datetime, float]] = []
    for i in range(days):
        ts = base + timedelta(days=i)
        trend = 1_200 + i * 9
        noise = rng.gauss(0, 90)
        value = max(0.0, trend + noise)
        points.append((ts, round(value, 2)))
    return points


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = auth_service.get_user_by_email(db, DEMO_EMAIL)
        if user is None:
            user = auth_service.create_user(
                db, DEMO_EMAIL, DEMO_PASSWORD, "Demo Analyst", role="analyst"
            )
            print(f"Created demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")

        revenue = dataset_service.create_dataset(
            db,
            user,
            DatasetCreate(
                name="Daily Revenue",
                slug="daily-revenue",
                description="Daily revenue across all channels with trend and weekly seasonality.",
                metric_type="revenue",
                unit="USD",
                currency="USD",
                granularity="day",
            ),
        )
        transactions = dataset_service.create_dataset(
            db,
            user,
            DatasetCreate(
                name="Daily Transactions",
                slug="daily-transactions",
                description="Number of successful payment transactions per day.",
                metric_type="transactions",
                unit="count",
                currency="USD",
                granularity="day",
            ),
        )

        existing = (
            db.query(MetricPoint).filter(MetricPoint.dataset_id == revenue.id).count()
        )
        if existing == 0:
            inserted, skipped = dataset_service.ingest_points(
                db,
                revenue,
                [PointCreate(timestamp=ts, value=v) for ts, v in _revenue_series()],
            )
            print(f"Seeded revenue dataset: {inserted} points (skipped {skipped} duplicates)")

        existing_tx = (
            db.query(MetricPoint).filter(MetricPoint.dataset_id == transactions.id).count()
        )
        if existing_tx == 0:
            inserted, skipped = dataset_service.ingest_points(
                db,
                transactions,
                [PointCreate(timestamp=ts, value=v) for ts, v in _transactions_series()],
            )
            print(f"Seeded transactions dataset: {inserted} points (skipped {skipped})")

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
