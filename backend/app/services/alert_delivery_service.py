"""Alert delivery execution: dispatch a pending AlertDelivery over its channel
and record the outcome (sent / failed) back on the row.

Channel senders degrade gracefully: the email channel is a logging stub, and
the slack/webhook channels fail closed when no URL is configured so a delivery
is never silently dropped.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.models.alert import Alert, AlertDelivery, DeliveryStatus

logger = logging.getLogger("infersight.delivery")

_HTTP_TIMEOUT = 8.0


class AlertDeliveryNotFoundError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def deliver(db, alert_id: int, delivery_id: int) -> str:
    """Execute the pending delivery and return its final status.

    Loads the delivery and its alert/dataset context, dispatches over the
    delivery's channel, and persists ``sent`` or ``failed`` accordingly.
    """
    delivery = db.get(AlertDelivery, delivery_id)
    if delivery is None:
        raise AlertDeliveryNotFoundError("delivery not found")
    alert = db.get(Alert, alert_id)
    if alert is None:
        _mark(db, delivery, DeliveryStatus.FAILED, "alert not found")
        return DeliveryStatus.FAILED.value
    dataset = alert.dataset if alert is not None else None
    if dataset is None:
        _mark(db, delivery, DeliveryStatus.FAILED, "dataset not found")
        return DeliveryStatus.FAILED.value

    try:
        if delivery.channel == "email":
            ok, error = _send_email(alert, dataset)
        elif delivery.channel == "slack":
            ok, error = _send_slack(alert, dataset)
        elif delivery.channel == "webhook":
            ok, error = _send_webhook(alert, dataset, delivery)
        else:
            ok, error = False, f"unknown channel: {delivery.channel}"
    except Exception as exc:  # network and serialization errors
        ok, error = False, f"{type(exc).__name__}: {exc}"

    if ok:
        _mark(db, delivery, DeliveryStatus.SENT)
        return DeliveryStatus.SENT.value
    _mark(db, delivery, DeliveryStatus.FAILED, error or "delivery failed")
    return DeliveryStatus.FAILED.value


def _mark(
    db,
    delivery: AlertDelivery,
    status: DeliveryStatus,
    error: str | None = None,
) -> None:
    delivery.status = status
    if status == DeliveryStatus.SENT:
        delivery.sent_at = _utcnow()
        delivery.error_message = None
    else:
        delivery.sent_at = None
        delivery.error_message = (error or "delivery failed")[:1024]
    db.add(delivery)
    db.commit()


def _send_email(alert: Alert, dataset) -> tuple[bool, str | None]:
    logger.info(
        "alert email stub: subject=%r body=%r dataset=%s",
        alert.title,
        alert.body,
        dataset.name,
    )
    return True, None


def _send_slack(alert: Alert, dataset) -> tuple[bool, str | None]:
    url = get_settings().slack_webhook_url
    if not url:
        return False, "SLACK_WEBHOOK_URL is not configured"
    payload = {
        "text": (
            f"[{alert.severity.upper()}] {dataset.name}: "
            f"{alert.body} (alert #{alert.id})"
        )
    }
    response = httpx.post(url, json=payload, timeout=_HTTP_TIMEOUT)
    if response.status_code >= 400:
        return False, f"slack webhook returned HTTP {response.status_code}"
    return True, None


def _send_webhook(
    alert: Alert, dataset, delivery: AlertDelivery
) -> tuple[bool, str | None]:
    rule = delivery.rule
    url = (rule.webhook_url if rule is not None else None) or ""
    if not url:
        return False, "no webhook URL configured for this rule"
    payload = {
        "event": "anomaly.alert",
        "alert_id": alert.id,
        "dataset_id": dataset.id,
        "dataset": dataset.name,
        "severity": alert.severity,
        "title": alert.title,
        "body": alert.body,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
    response = httpx.post(url, json=payload, timeout=_HTTP_TIMEOUT)
    if response.status_code >= 400:
        return False, f"webhook returned HTTP {response.status_code}"
    return True, None
