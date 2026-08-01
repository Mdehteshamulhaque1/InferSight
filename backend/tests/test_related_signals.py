"""Tests for anomaly correlation (related signals): the service function,
the /related endpoint, and the root-cause integration."""

from __future__ import annotations

from sqlalchemy import select

from app.models.dataset import MetricPoint
from app.services.analytics_service import find_related_datasets
from app.services.anomaly_service import detect
from tests.conftest import make_series


def _spiky_series():
    points = make_series(days=60, base=100, step=1, seed=1)
    points[40]["value"] = 1000  # massive spike
    points[45]["value"] = 10  # massive drop
    return points


def _mk_dataset(client, headers, org_id, name, points, granularity="day"):
    payload = {"name": name, "metric_type": "custom", "granularity": granularity}
    if org_id is not None:
        payload["organization_id"] = org_id
    resp = client.post("/api/v1/datasets", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    dataset_id = resp.json()["id"]
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=headers, json={"points": points}
    )
    assert resp.status_code == 200, resp.text
    return dataset_id


def _seed_org(client, headers):
    """Create an org with the anomaly dataset plus same/opposite/weak/sparse peers."""
    org = client.post(
        "/api/v1/organizations", headers=headers, json={"name": "Signal Org"}
    )
    assert org.status_code == 201, org.text
    org_id = org.json()["id"]

    spiky = _spiky_series()
    anomaly_id = _mk_dataset(client, headers, org_id, "Core", spiky)
    same_id = _mk_dataset(client, headers, org_id, "Same", spiky)
    opposite_id = _mk_dataset(
        client,
        headers,
        org_id,
        "Opposite",
        [
            {"timestamp": p["timestamp"], "value": round(300 - p["value"], 6)}
            for p in spiky
        ],
    )
    # Zero-variance series: correlation is exactly 0.0, below the threshold.
    weak_id = _mk_dataset(
        client,
        headers,
        org_id,
        "Weak",
        [{"timestamp": p["timestamp"], "value": 100.0} for p in spiky],
    )
    # Only three points: never enough overlap inside the window.
    sparse_id = _mk_dataset(
        client, headers, org_id, "Sparse", make_series(days=3, base=100, step=1, seed=2)
    )
    return anomaly_id, same_id, opposite_id, weak_id, sparse_id


def _load_points(db_session, dataset_id):
    return list(
        db_session.scalars(
            select(MetricPoint)
            .where(MetricPoint.dataset_id == dataset_id)
            .order_by(MetricPoint.timestamp.asc())
        ).all()
    )


# --------------------------------------------------------------------------- #
# Service function
# --------------------------------------------------------------------------- #
def test_find_related_datasets_labels_direction(client, user_headers, db_session):
    anomaly_id, same_id, opposite_id, weak_id, sparse_id = _seed_org(client, user_headers)

    anomaly = detect(_load_points(db_session, anomaly_id)).anomalies[0]
    assert anomaly.dataset_id == anomaly_id
    signals = find_related_datasets(anomaly, db_session)

    by_id = {s["dataset_id"]: s for s in signals}
    assert set(by_id) == {same_id, opposite_id}
    assert by_id[same_id]["direction"] == "same"
    assert by_id[same_id]["correlation"] > 0.6
    assert by_id[opposite_id]["direction"] == "opposite"
    assert by_id[opposite_id]["correlation"] < -0.6
    assert weak_id not in by_id
    assert sparse_id not in by_id
    assert signals == sorted(signals, key=lambda s: abs(s["correlation"]), reverse=True)
    assert len(signals) <= 5


def test_find_related_datasets_below_threshold(client, user_headers, db_session):
    org = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Weak Org"}
    )
    org_id = org.json()["id"]
    spiky = _spiky_series()
    anomaly_id = _mk_dataset(client, user_headers, org_id, "Core", spiky)
    _mk_dataset(
        client,
        user_headers,
        org_id,
        "Flat",
        [{"timestamp": p["timestamp"], "value": 100.0} for p in spiky],
    )

    anomaly = detect(_load_points(db_session, anomaly_id)).anomalies[0]
    assert find_related_datasets(anomaly, db_session) == []


def test_find_related_datasets_insufficient_overlap(client, user_headers, db_session):
    org = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Sparse Org"}
    )
    org_id = org.json()["id"]
    anomaly_id = _mk_dataset(client, user_headers, org_id, "Core", _spiky_series())
    _mk_dataset(
        client, user_headers, org_id, "Barely", make_series(days=3, base=100, step=1, seed=2)
    )

    anomaly = detect(_load_points(db_session, anomaly_id)).anomalies[0]
    assert find_related_datasets(anomaly, db_session) == []


def test_find_related_datasets_no_other_datasets(client, user_headers, db_session):
    org = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Lonely Org"}
    )
    anomaly_id = _mk_dataset(
        client, user_headers, org.json()["id"], "Solo", _spiky_series()
    )
    anomaly = detect(_load_points(db_session, anomaly_id)).anomalies[0]
    assert find_related_datasets(anomaly, db_session) == []


def test_find_related_datasets_without_org(client, user_headers, db_session):
    anomaly_id = _mk_dataset(client, user_headers, None, "Personal", _spiky_series())
    anomaly = detect(_load_points(db_session, anomaly_id)).anomalies[0]
    assert find_related_datasets(anomaly, db_session) == []


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
def test_related_endpoint(client, user_headers):
    anomaly_id, same_id, opposite_id, weak_id, sparse_id = _seed_org(client, user_headers)
    resp = client.get(
        f"/api/v1/datasets/{anomaly_id}/anomalies/0/related", headers=user_headers
    )
    assert resp.status_code == 200, resp.text
    by_id = {s["dataset_id"]: s for s in resp.json()}
    assert set(by_id) == {same_id, opposite_id}
    assert weak_id not in by_id and sparse_id not in by_id


def test_related_endpoint_no_other_datasets(client, user_headers):
    org = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Empty Org"}
    )
    anomaly_id = _mk_dataset(
        client, user_headers, org.json()["id"], "Alone", _spiky_series()
    )
    resp = client.get(
        f"/api/v1/datasets/{anomaly_id}/anomalies/0/related", headers=user_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_related_endpoint_bad_index(client, user_headers):
    anomaly_id, *_ = _seed_org(client, user_headers)
    resp = client.get(
        f"/api/v1/datasets/{anomaly_id}/anomalies/99/related", headers=user_headers
    )
    assert resp.status_code == 404


def test_related_endpoint_access_denied(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "stranger@test.dev",
            "password": "Password123",
            "full_name": "Stranger",
        },
    )
    stranger = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/anomalies/0/related", headers=stranger
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #
def test_related_endpoint_caches(client, user_headers, monkeypatch):
    anomaly_id, *_ = _seed_org(client, user_headers)
    calls = {"n": 0}
    fixed = [{"dataset_id": 1, "dataset_name": "x", "correlation": 0.9, "direction": "same"}]

    def fake(anomaly, db_session):
        calls["n"] += 1
        return fixed

    monkeypatch.setattr("app.services.analytics_service.find_related_datasets", fake)

    resp1 = client.get(
        f"/api/v1/datasets/{anomaly_id}/anomalies/0/related", headers=user_headers
    )
    resp2 = client.get(
        f"/api/v1/datasets/{anomaly_id}/anomalies/0/related", headers=user_headers
    )
    assert resp1.status_code == 200 and resp2.status_code == 200
    assert resp1.json() == fixed == resp2.json()
    assert calls["n"] == 1


# --------------------------------------------------------------------------- #
# Root-cause integration
# --------------------------------------------------------------------------- #
def test_root_cause_includes_related_signals(client, user_headers):
    anomaly_id, same_id, *_ = _seed_org(client, user_headers)
    resp = client.get(f"/api/v1/datasets/{anomaly_id}/root-cause", headers=user_headers)
    assert resp.status_code == 200
    signals = resp.json()["related_signals"]
    assert any(s["dataset_id"] == same_id and s["direction"] == "same" for s in signals)
