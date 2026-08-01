"""Tests for alert routing: rule CRUD, severity matching, cooldown gating,
delivery execution, escalation, and the deliveries API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.alert import Alert, AlertDelivery, DeliveryStatus, SeverityLevel
from app.services.alert_delivery_service import AlertDeliveryNotFoundError, deliver
from app.services.anomaly_service import escalate_critical_alerts, route_alert
from tests.conftest import make_series


def _spiky_dataset(client, headers) -> int:
    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": "Alert Spikes", "metric_type": "custom", "granularity": "day"},
    )
    assert resp.status_code == 201, resp.text
    dataset_id = resp.json()["id"]
    points = make_series(days=60, base=100, step=1)
    points[40]["value"] = 1000
    points[45]["value"] = 10
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=headers, json={"points": points}
    )
    assert resp.status_code == 200, resp.text
    return dataset_id


def _make_rule(client, headers, dataset_id, **overrides) -> dict:
    payload = {
        "dataset_id": dataset_id,
        "severity_threshold": "warning",
        "channels": ["email"],
        "cooldown_minutes": 30,
    }
    payload.update(overrides)
    resp = client.post("/api/v1/alert-rules", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _me(client, headers) -> dict:
    return client.get("/api/v1/auth/me", headers=headers).json()


def _make_alert(db, user_id, dataset_id, severity, title, when=None) -> Alert:
    alert = Alert(
        user_id=user_id,
        dataset_id=dataset_id,
        kind="anomaly",
        severity=severity,
        title=title,
        body="test alert body",
        is_read=False,
        created_at=when or datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


# --------------------------------------------------------------------------- #
# Rule CRUD
# --------------------------------------------------------------------------- #
def test_rule_lifecycle(client, user_headers, seeded_dataset):
    rule = _make_rule(
        client,
        user_headers,
        seeded_dataset,
        severity_threshold="critical",
        channels=["email", "webhook"],
        webhook_url="https://hooks.example.com/x",
        cooldown_minutes=15,
    )
    assert rule["severity_threshold"] == "critical"
    assert rule["channels"] == ["email", "webhook"]
    assert rule["cooldown_minutes"] == 15
    assert rule["is_active"] is True
    assert rule["webhook_url"] == "https://hooks.example.com/x"

    resp = client.get(
        "/api/v1/alert-rules", headers=user_headers, params={"dataset_id": seeded_dataset}
    )
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["items"]] == [rule["id"]]

    resp = client.patch(
        f"/api/v1/alert-rules/{rule['id']}",
        headers=user_headers,
        json={"severity_threshold": "warning", "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["severity_threshold"] == "warning"
    assert resp.json()["is_active"] is False
    assert resp.json()["channels"] == ["email", "webhook"]

    resp = client.delete(f"/api/v1/alert-rules/{rule['id']}", headers=user_headers)
    assert resp.status_code == 200
    resp = client.patch(f"/api/v1/alert-rules/{rule['id']}", headers=user_headers, json={})
    assert resp.status_code == 404


def test_rule_create_validates_channels_and_cooldown(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/alert-rules",
        headers=user_headers,
        json={"dataset_id": seeded_dataset, "channels": []},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/v1/alert-rules",
        headers=user_headers,
        json={"dataset_id": seeded_dataset, "cooldown_minutes": 0},
    )
    assert resp.status_code == 422


def test_rule_requires_dataset_access(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/alert-rules",
        headers=user_headers,
        json={"dataset_id": 99999, "channels": ["email"]},
    )
    assert resp.status_code == 404

    # A second user who does not own/share the dataset cannot create a rule.
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "stranger@test.dev", "password": "Password123", "full_name": "Stranger"},
    )
    stranger = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.post(
        "/api/v1/alert-rules",
        headers=stranger,
        json={"dataset_id": seeded_dataset, "channels": ["email"]},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Severity matching & cooldown (service level)
# --------------------------------------------------------------------------- #
def test_severity_matching(client, user_headers, seeded_dataset, db_session):
    me = _me(client, user_headers)
    _make_rule(client, user_headers, seeded_dataset, severity_threshold="warning")
    _make_rule(client, user_headers, seeded_dataset, severity_threshold="critical")

    warning_alert = _make_alert(db_session, me["id"], seeded_dataset, "warning", "w1")
    assert route_alert(db_session, warning_alert) == 1

    critical_alert = _make_alert(db_session, me["id"], seeded_dataset, "critical", "c1")
    assert route_alert(db_session, critical_alert) == 2

    statuses = {
        d.status.value for d in db_session.scalars(select(AlertDelivery)).all()
    }
    assert statuses == {"pending"}


def test_inactive_rule_skipped(client, user_headers, seeded_dataset, db_session):
    me = _me(client, user_headers)
    _make_rule(client, user_headers, seeded_dataset, is_active=False)
    alert = _make_alert(db_session, me["id"], seeded_dataset, "critical", "inactive")
    assert route_alert(db_session, alert) == 0


def test_cooldown_blocks_then_elapses(client, user_headers, seeded_dataset, db_session):
    me = _me(client, user_headers)
    rule = _make_rule(
        client, user_headers, seeded_dataset, cooldown_minutes=30, channels=["email"]
    )

    first = _make_alert(db_session, me["id"], seeded_dataset, "critical", "cooldown-1")
    assert route_alert(db_session, first) == 1

    delivery = db_session.scalars(select(AlertDelivery)).one()
    delivery.status = DeliveryStatus.SENT
    delivery.sent_at = datetime.now(timezone.utc)
    db_session.commit()

    second = _make_alert(db_session, me["id"], seeded_dataset, "critical", "cooldown-2")
    assert route_alert(db_session, second) == 0

    delivery.sent_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()
    third = _make_alert(db_session, me["id"], seeded_dataset, "critical", "cooldown-3")
    assert route_alert(db_session, third) == 1

    assert len(db_session.scalars(select(AlertDelivery)).all()) == 2
    assert rule["id"]


# --------------------------------------------------------------------------- #
# Delivery execution
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


def test_webhook_delivery_success_and_failure(
    client, user_headers, seeded_dataset, db_session, monkeypatch
):
    me = _me(client, user_headers)
    _make_rule(
        client,
        user_headers,
        seeded_dataset,
        channels=["webhook"],
        webhook_url="https://hooks.example.com/x",
    )
    alert = _make_alert(db_session, me["id"], seeded_dataset, "critical", "hook")
    assert route_alert(db_session, alert) == 1
    delivery = db_session.scalars(select(AlertDelivery)).one()

    monkeypatch.setattr(
        "app.services.alert_delivery_service.httpx.post",
        lambda *a, **k: _FakeResponse(200),
    )
    assert deliver(db_session, alert.id, delivery.id) == "sent"
    db_session.refresh(delivery)
    assert delivery.status == DeliveryStatus.SENT
    assert delivery.sent_at is not None
    assert delivery.error_message is None

    monkeypatch.setattr(
        "app.services.alert_delivery_service.httpx.post",
        lambda *a, **k: _FakeResponse(500),
    )
    # Move the first delivery out of the cooldown window so a second attempt routes.
    delivery.sent_at = datetime.now(timezone.utc) - timedelta(minutes=40)
    db_session.commit()
    second = _make_alert(db_session, me["id"], seeded_dataset, "critical", "hook-2")
    assert route_alert(db_session, second) == 1
    failed = db_session.scalars(select(AlertDelivery)).all()[1]
    assert deliver(db_session, second.id, failed.id) == "failed"
    db_session.refresh(failed)
    assert failed.status == DeliveryStatus.FAILED
    assert "HTTP 500" in failed.error_message
    assert failed.sent_at is None


def test_webhook_delivery_without_url_fails(
    client, user_headers, seeded_dataset, db_session
):
    me = _me(client, user_headers)
    _make_rule(client, user_headers, seeded_dataset, channels=["webhook"])
    alert = _make_alert(db_session, me["id"], seeded_dataset, "critical", "hookless")
    assert route_alert(db_session, alert) == 1
    delivery = db_session.scalars(select(AlertDelivery)).one()
    assert deliver(db_session, alert.id, delivery.id) == "failed"
    db_session.refresh(delivery)
    assert "no webhook URL configured" in delivery.error_message


def test_deliver_missing_delivery_raises(db_session, seeded_dataset):
    try:
        deliver(db_session, 1, 999999)
        raise AssertionError("expected AlertDeliveryNotFoundError")
    except AlertDeliveryNotFoundError:
        pass


# --------------------------------------------------------------------------- #
# Escalation
# --------------------------------------------------------------------------- #
def test_escalate_critical_alerts(client, user_headers, seeded_dataset, db_session):
    me = _me(client, user_headers)
    _make_rule(
        client, user_headers, seeded_dataset, channels=["email"], cooldown_minutes=1
    )

    critical = _make_alert(
        db_session,
        me["id"],
        seeded_dataset,
        SeverityLevel.CRITICAL.value,
        "escalate-critical",
        when=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    old_read = _make_alert(
        db_session,
        me["id"],
        seeded_dataset,
        SeverityLevel.CRITICAL.value,
        "escalate-read",
        when=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    old_read.is_read = True
    db_session.commit()

    result = escalate_critical_alerts(db_session)
    assert result["critical_alerts"] == 1
    assert result["deliveries_created"] == 1
    assert result["skipped_in_cooldown"] == 0

    delivery = db_session.scalars(select(AlertDelivery)).one()
    delivery.status = DeliveryStatus.SENT
    delivery.sent_at = datetime.now(timezone.utc)
    db_session.commit()

    result = escalate_critical_alerts(db_session)
    assert result["deliveries_created"] == 0
    assert result["skipped_in_cooldown"] == 1

    assert critical.id and old_read.id


# --------------------------------------------------------------------------- #
# Routing through sync + deliveries API
# --------------------------------------------------------------------------- #
def test_sync_routes_alerts_and_lists_deliveries(client, user_headers, db_session):
    dataset_id = _spiky_dataset(client, user_headers)
    rule = _make_rule(client, user_headers, dataset_id, channels=["email"])

    resp = client.post(f"/api/v1/alerts/sync/{dataset_id}", headers=user_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["alerts_created"] >= 2

    alerts = client.get("/api/v1/alerts", headers=user_headers).json()["items"]
    deliveries = db_session.scalars(select(AlertDelivery)).all()
    assert len(deliveries) >= 1
    assert {d.rule_id for d in deliveries} == {rule["id"]}
    assert {d.status for d in deliveries} == {DeliveryStatus.PENDING}

    resp = client.get(
        f"/api/v1/alerts/{alerts[0]['id']}/deliveries", headers=user_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["channel"] == "email"
        assert item["status"] in ("pending", "sent", "failed")


def test_deliveries_scoped_to_owner(client, user_headers, db_session):
    dataset_id = _spiky_dataset(client, user_headers)
    _make_rule(client, user_headers, dataset_id, channels=["email"])
    client.post(f"/api/v1/alerts/sync/{dataset_id}", headers=user_headers)
    alert_id = client.get("/api/v1/alerts", headers=user_headers).json()["items"][0]["id"]

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "other@test.dev", "password": "Password123", "full_name": "Other"},
    )
    other = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get(f"/api/v1/alerts/{alert_id}/deliveries", headers=other)
    assert resp.status_code == 403
