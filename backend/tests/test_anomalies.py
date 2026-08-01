"""Anomaly detection tests."""

from __future__ import annotations

from tests.conftest import make_series


def test_anomaly_detection_finds_spike(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Anomalous", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]

    points = make_series(days=60, base=100, step=1)
    points[40]["value"] = 1000  # massive spike
    points[45]["value"] = 10  # massive drop
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": points}
    )

    resp = client.get(
        f"/api/v1/anomalies/datasets/{dataset_id}",
        headers=user_headers,
        params={"threshold": 3.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 60
    assert data["summary"]["total"] >= 2

    directions = {a["direction"] for a in data["anomalies"]}
    assert {"spike", "drop"} <= directions
    critical = [a for a in data["anomalies"] if a["severity"] == "critical"]
    assert len(critical) >= 2
    for anomaly in critical:
        # score sign encodes direction (drops are negative, spikes positive).
        assert abs(anomaly["score"]) >= 2 * 3.0
        assert anomaly["reason"]


def test_anomaly_detection_clean_series(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Clean", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    points = make_series(days=40, base=100, step=0.1, seed=3)
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": points}
    )
    resp = client.get(
        f"/api/v1/anomalies/datasets/{dataset_id}",
        headers=user_headers,
        params={"threshold": 5.0},
    )
    assert resp.status_code == 200
    assert resp.json()["summary"]["total"] == 0


def test_anomaly_detection_requires_min_points(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Short", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    points = make_series(days=5)
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": points}
    )
    resp = client.get(f"/api/v1/anomalies/datasets/{dataset_id}", headers=user_headers)
    assert resp.status_code == 422


def test_anomaly_window_parameter(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/anomalies/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"window": 14, "threshold": 3.0},
    )
    assert resp.status_code == 200
    assert resp.json()["window"] == 14
