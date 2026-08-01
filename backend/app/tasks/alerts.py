"""Celery tasks for alert delivery and escalation.

Each task owns its database session, so it can run in the worker process
independently of the request lifecycle. Delivery status is updated by
``alert_delivery_service.deliver`` as the side effect of execution.
"""

from __future__ import annotations

from app.core.celery_app import celery_app
from app.database.session import SessionLocal
from app.services.alert_delivery_service import deliver
from app.services.anomaly_service import escalate_critical_alerts as escalate


@celery_app.task(name="app.tasks.send_alert_email")
def send_alert_email(alert_id: int, delivery_id: int) -> str:
    """Deliver an alert over the email channel (logging stub)."""
    with SessionLocal() as db:
        return deliver(db, alert_id, delivery_id)


@celery_app.task(name="app.tasks.send_alert_slack")
def send_alert_slack(alert_id: int, delivery_id: int) -> str:
    """Deliver an alert over Slack via the configured webhook URL."""
    with SessionLocal() as db:
        return deliver(db, alert_id, delivery_id)


@celery_app.task(name="app.tasks.send_alert_webhook")
def send_alert_webhook(alert_id: int, delivery_id: int) -> str:
    """Deliver an alert over the rule-specific webhook URL."""
    with SessionLocal() as db:
        return deliver(db, alert_id, delivery_id)


@celery_app.task(name="app.tasks.escalate_critical_alerts")
def escalate_critical_alerts() -> dict:
    """Re-trigger delivery for unacknowledged critical alerts.

    Runs on a five-minute beat schedule; see ``app.core.celery_app``.
    """
    with SessionLocal() as db:
        return escalate(db)
