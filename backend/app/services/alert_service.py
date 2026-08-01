"""Alert persistence: turn anomaly detections into durable, deduplicable alerts,
manage alert routing rules, and expose per-alert delivery history."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertDelivery, AlertRule
from app.models.user import User
from app.schemas.alert_rules import AlertRuleCreate, AlertRuleUpdate
from app.services.anomaly_service import route_alert

logger = logging.getLogger("infersight.alerts")


class AlertNotFoundError(Exception):
    pass


class AlertAccessError(Exception):
    pass


class AlertRuleNotFoundError(Exception):
    pass


def _title_for(anomaly) -> str:
    ts = anomaly.timestamp
    return f"Anomaly {anomaly.direction} — {ts.strftime('%Y-%m-%d %H:%M')} UTC"


def sync_alerts_from_anomalies(
    db: Session,
    user: User,
    dataset_id: int,
    anomalies: list,
    limit: int = 25,
) -> int:
    """Persist alerts for anomalies, skipping events already alerted on.

    Each newly created alert is routed through its dataset's active rules,
    which enqueues channel deliveries; routing failures never abort the sync.
    """
    created = 0
    existing_titles = set(
        db.scalars(
            select(Alert.title).where(
                Alert.dataset_id == dataset_id,
                Alert.kind == "anomaly",
            )
        ).all()
    )
    for anomaly in anomalies:
        if created >= limit:
            break
        title = _title_for(anomaly)
        if title in existing_titles:
            continue
        severity = anomaly.severity
        body = (
            f"{anomaly.direction} on {anomaly.timestamp.strftime('%Y-%m-%d %H:%M')} "
            f"UTC: {anomaly.reason}. Expected {anomaly.expected:,.2f}, "
            f"observed {anomaly.value:,.2f} (score {anomaly.score:.1f}σ)."
        )
        alert = Alert(
            user_id=user.id,
            dataset_id=dataset_id,
            kind="anomaly",
            severity=severity,
            title=title,
            body=body,
            is_read=False,
        )
        db.add(alert)
        db.flush()
        existing_titles.add(title)
        created += 1
        try:
            route_alert(db, alert)
        except Exception:
            logger.exception("alert routing failed for alert %s", alert.id)
    db.commit()
    return created


def create_alert(
    db: Session,
    user: User,
    dataset_id: int | None,
    kind: str,
    severity: str,
    title: str,
    body: str,
) -> Alert:
    existing = db.scalar(
        select(Alert).where(
            Alert.dataset_id == dataset_id,
            Alert.kind == kind,
            Alert.title == title,
        )
    )
    if existing is not None:
        return existing
    alert = Alert(
        user_id=user.id,
        dataset_id=dataset_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        is_read=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(
    db: Session, user: User, unread_only: bool = False, limit: int = 50
) -> list[Alert]:
    query = select(Alert).where(Alert.user_id == user.id)
    if unread_only:
        query = query.where(Alert.is_read == False)  # noqa: E712
    return list(db.scalars(query.order_by(Alert.created_at.desc()).limit(limit)).all())


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Alert.id)).where(
            Alert.user_id == user.id, Alert.is_read == False  # noqa: E712
        )
    ) or 0


def mark_read(db: Session, user: User, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AlertNotFoundError("alert not found")
    if alert.user_id != user.id:
        raise AlertAccessError("you do not have access to this alert")
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


def mark_all_read(db: Session, user: User) -> int:
    alerts = db.scalars(
        select(Alert).where(
            Alert.user_id == user.id, Alert.is_read == False  # noqa: E712
        )
    ).all()
    for alert in alerts:
        alert.is_read = True
    db.commit()
    return len(alerts)


# --------------------------------------------------------------------------- #
# Alert routing rules
# --------------------------------------------------------------------------- #
def get_rule(db: Session, rule_id: int) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise AlertRuleNotFoundError("alert rule not found")
    return rule


def list_rules(
    db: Session, dataset_id: int | None = None, limit: int = 100
) -> list[AlertRule]:
    query = select(AlertRule).order_by(AlertRule.created_at.desc())
    if dataset_id is not None:
        query = query.where(AlertRule.dataset_id == dataset_id)
    return list(db.scalars(query.limit(limit)).all())


def create_rule(db: Session, dataset_id: int, payload: AlertRuleCreate) -> AlertRule:
    rule = AlertRule(
        dataset_id=dataset_id,
        severity_threshold=payload.severity_threshold,
        channels=[channel.value for channel in payload.channels],
        cooldown_minutes=payload.cooldown_minutes,
        is_active=payload.is_active,
        webhook_url=payload.webhook_url,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule: AlertRule, payload: AlertRuleUpdate) -> AlertRule:
    updates = payload.model_dump(exclude_unset=True)
    if "channels" in updates and updates["channels"] is not None:
        updates["channels"] = [channel.value for channel in updates["channels"]]
    for field, value in updates.items():
        setattr(rule, field, value)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule: AlertRule) -> None:
    db.delete(rule)
    db.commit()


def list_deliveries_for_alert(
    db: Session, user: User, alert_id: int
) -> list[AlertDelivery]:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise AlertNotFoundError("alert not found")
    if alert.user_id != user.id:
        raise AlertAccessError("you do not have access to this alert")
    return list(
        db.scalars(
            select(AlertDelivery)
            .where(AlertDelivery.alert_id == alert.id)
            .order_by(AlertDelivery.created_at.desc())
        ).all()
    )
