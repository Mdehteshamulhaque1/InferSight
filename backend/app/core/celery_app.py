"""Celery application for asynchronous alert delivery.

Wired to the same Redis instance used for caching by default; set
``CELERY_BROKER_URL`` to point at a dedicated broker (or a different Redis
logical DB) when the cache and queue should be separated.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "infersight",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_broker_url or settings.redis_url,
    include=["app.tasks.alerts"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Re-trigger delivery for unacknowledged critical alerts every 5 minutes.
        "escalate-critical-alerts": {
            "task": "app.tasks.escalate_critical_alerts",
            "schedule": 300.0,
        },
    },
)
