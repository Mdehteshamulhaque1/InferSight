"""Anomaly detection engine.

Implements a robust rolling z-score detector: each point is compared against
a trailing window's median and scaled median absolute deviation (MAD). Median
and MAD are resistant to outliers, so a single extreme value in the baseline
window cannot mask a genuine anomaly (e.g. a spike cannot hide a drop that
immediately follows it). The rolling scale is floored at the full-series
scale, since a 7-point MAD is a noisy estimate that collapses on tight
windows and would otherwise over-flag borderline noise. When the trailing
window is too small, full-series robust statistics are used as a fallback so
early points are still evaluated.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.models.alert import (
    Alert,
    AlertDelivery,
    AlertRule,
    DeliveryStatus,
    SeverityLevel,
)
from app.schemas.anomaly import Anomaly, AnomalyResponse

logger = logging.getLogger("infersight.anomalies")

_MAD_NORMALIZER = 0.6744897501960817  # 1 / Phi^-1(3/4)

# Detection severity to rule threshold ranking: a rule whose threshold is at or
# below the detected severity matches.
_SEVERITY_RANK = {SeverityLevel.WARNING.value: 1, SeverityLevel.CRITICAL.value: 2}

_DELIVERY_TASKS = {
    "email": "app.tasks.send_alert_email",
    "slack": "app.tasks.send_alert_slack",
    "webhook": "app.tasks.send_alert_webhook",
}


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _robust_stats(values: list[float]) -> tuple[float, float]:
    """Return (median, scaled MAD). MAD is scaled so it matches the standard
    deviation scale for normally distributed data."""
    if not values:
        return 0.0, 0.0
    median = _median(values)
    deviations = [abs(v - median) for v in values]
    mad = _median(deviations)
    return median, mad * _MAD_NORMALIZER


def detect(
    points: list[object],
    window: int = 7,
    threshold: float = 3.0,
    min_points: int = 6,
) -> AnomalyResponse:
    """Detect anomalies in a chronologically ordered series."""
    if threshold <= 0:
        threshold = 3.0
    if window < 2:
        window = 7

    values = [p.value for p in points]
    timestamps = [p.timestamp for p in points]
    total = len(values)
    anomalies: list[Anomaly] = []

    global_median, global_scale = _robust_stats(values)
    if global_scale == 0.0:
        global_scale = 1e-12

    for i, value in enumerate(values):
        if total < min_points:
            continue
        start = max(0, i - window)
        # Trailing window must exclude the current point for a true "rolling" baseline.
        window_values = values[start:i]
        if len(window_values) >= 3:
            median, scale = _robust_stats(window_values)
            # A 7-point MAD is a noisy scale estimate and collapses on tight
            # windows, producing over-sensitivity. Floor it at the full-series
            # scale (a stable estimate) to stay immune to that noise while the
            # rolling median keeps detecting local level shifts.
            scale = max(scale, global_scale)
        else:
            median, scale = global_median, global_scale

        score = (value - median) / scale
        if abs(score) < threshold:
            continue

        direction = "spike" if value > median else "drop"
        severity = "critical" if abs(score) >= 2 * threshold else "warning"
        reason = (
            f"value {value:,.2f} deviates {abs(score):.2f}σ "
            f"{'above' if value > median else 'below'} the "
            f"expected {median:,.2f}"
        )
        anomalies.append(
            Anomaly(
                dataset_id=points[0].dataset_id if points else None,
                timestamp=timestamps[i],
                value=round(value, 6),
                expected=round(median, 6),
                score=round(score, 4),
                severity=severity,
                direction=direction,
                reason=reason,
            )
        )

    summary = {
        "total": len(anomalies),
        "spikes": sum(1 for a in anomalies if a.direction == "spike"),
        "drops": sum(1 for a in anomalies if a.direction == "drop"),
        "warning": sum(1 for a in anomalies if a.severity == "warning"),
        "critical": sum(1 for a in anomalies if a.severity == "critical"),
    }
    return AnomalyResponse(
        dataset_id=points[0].dataset_id if points else 0,
        method="rolling_robust_zscore",
        window=window,
        threshold=threshold,
        total_points=total,
        anomalies=anomalies,
        summary=summary,
    )


# --------------------------------------------------------------------------- #
# Alert routing
# --------------------------------------------------------------------------- #
def _matches_severity(rule: AlertRule, detected_severity: str) -> bool:
    """True when a rule's threshold is at or below the detected severity."""
    threshold = getattr(rule.severity_threshold, "value", rule.severity_threshold)
    return _SEVERITY_RANK.get(detected_severity, 0) >= _SEVERITY_RANK.get(
        str(threshold), 2
    )


def _in_cooldown(db: Session, rule: AlertRule) -> bool:
    """True when a delivery for this rule was sent within the rule's cooldown."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=rule.cooldown_minutes)
    recent = db.scalar(
        select(AlertDelivery.id)
        .where(
            AlertDelivery.rule_id == rule.id,
            AlertDelivery.status == DeliveryStatus.SENT,
            AlertDelivery.sent_at >= cutoff,
        )
        .limit(1)
    )
    return recent is not None


def _enqueue_delivery(delivery: AlertDelivery) -> None:
    """Queue the delivery's channel task. Broker failures degrade gracefully."""
    if not get_settings().celery_enabled:
        return
    task_name = _DELIVERY_TASKS.get(delivery.channel)
    if task_name is None:
        return
    try:
        celery_app.send_task(task_name, args=[delivery.alert_id, delivery.id])
    except Exception:
        logger.exception(
            "failed to enqueue %s delivery for alert %s",
            delivery.channel,
            delivery.alert_id,
        )


def route_alert(db: Session, alert: Alert) -> int:
    """Route a persisted alert through matching active rules.

    For every active rule on the alert's dataset whose threshold is at or below
    the alert severity and whose cooldown has elapsed, one ``AlertDelivery``
    row is created per channel and its Celery task is enqueued. Returns the
    number of deliveries created.
    """
    if alert.dataset_id is None:
        return 0
    rules = db.scalars(
        select(AlertRule).where(
            AlertRule.dataset_id == alert.dataset_id,
            AlertRule.is_active.is_(True),
        )
    ).all()
    created = 0
    for rule in rules:
        if not _matches_severity(rule, alert.severity):
            continue
        if _in_cooldown(db, rule):
            continue
        for channel in rule.channels:
            delivery = AlertDelivery(
                alert_id=alert.id,
                rule_id=rule.id,
                channel=channel,
                status=DeliveryStatus.PENDING,
            )
            db.add(delivery)
            db.flush()
            _enqueue_delivery(delivery)
            created += 1
    db.commit()
    return created


def escalate_critical_alerts(db: Session, within_hours: int = 24) -> dict:
    """Re-trigger delivery for unacknowledged critical alerts (escalation).

    Runs on the five-minute beat schedule. Alerts are eligible when they are
    critical, created within ``within_hours``, not yet read, and each matching
    rule's cooldown has elapsed since its last sent delivery.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    alerts = db.scalars(
        select(Alert).where(
            Alert.severity == SeverityLevel.CRITICAL.value,
            Alert.is_read.is_(False),
            Alert.created_at >= cutoff,
        )
    ).all()
    created = 0
    skipped = 0
    for alert in alerts:
        if alert.dataset_id is None:
            continue
        rules = db.scalars(
            select(AlertRule).where(
                AlertRule.dataset_id == alert.dataset_id,
                AlertRule.is_active.is_(True),
            )
        ).all()
        for rule in rules:
            if not _matches_severity(rule, alert.severity):
                continue
            if _in_cooldown(db, rule):
                skipped += 1
                continue
            for channel in rule.channels:
                delivery = AlertDelivery(
                    alert_id=alert.id,
                    rule_id=rule.id,
                    channel=channel,
                    status=DeliveryStatus.PENDING,
                )
                db.add(delivery)
                db.flush()
                _enqueue_delivery(delivery)
                created += 1
    db.commit()
    return {
        "critical_alerts": len(alerts),
        "deliveries_created": created,
        "skipped_in_cooldown": skipped,
    }
