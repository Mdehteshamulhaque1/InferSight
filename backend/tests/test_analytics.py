"""Analytics endpoint tests."""

from __future__ import annotations

from tests.conftest import make_series


def test_analytics_full_response(client, user_headers, seeded_dataset):
    resp = client.get(f"/api/v1/analytics/datasets/{seeded_dataset}", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset"]["point_count"] == 45
    assert data["period"]["start"]
    assert len(data["series"]) == 45

    kpi_keys = {k["key"] for k in data["kpis"]}
    assert {"total", "average", "latest", "peak", "trough", "growth"} <= kpi_keys
    total = next(k for k in data["kpis"] if k["key"] == "total")
    assert total["value"] > 0

    assert data["trend"]["direction"] == "up"
    assert data["trend"]["slope"] > 0
    assert 0 <= data["trend"]["r_squared"] <= 1
    assert len(data["trend"]["fitted"]) == 45


def test_analytics_resampling_week(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/analytics/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"granularity": "week"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["series"]) < 45
    assert len(data["kpis"]) == 6


def test_analytics_is_cached(client, user_headers, seeded_dataset):
    url = f"/api/v1/analytics/datasets/{seeded_dataset}"
    first = client.get(url, headers=user_headers)
    second = client.get(url, headers=user_headers)
    assert first.json() == second.json()


def test_analytics_respects_max_points(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/analytics/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"max_points": 20},
    )
    assert resp.status_code == 200
    assert resp.json()["dataset"]["point_count"] == 20
    assert len(resp.json()["series"]) == 20


def test_analytics_requires_auth(client, seeded_dataset):
    assert client.get(f"/api/v1/analytics/datasets/{seeded_dataset}").status_code == 401


def test_analytics_nonexistent_dataset(client, user_headers):
    resp = client.get("/api/v1/analytics/datasets/99999", headers=user_headers)
    assert resp.status_code == 404


def test_kpis_series_trend_endpoints(client, user_headers, seeded_dataset):
    kpis = client.get(
        f"/api/v1/analytics/datasets/{seeded_dataset}/kpis", headers=user_headers
    )
    assert kpis.status_code == 200
    assert len(kpis.json()) == 6

    series = client.get(
        f"/api/v1/analytics/datasets/{seeded_dataset}/series", headers=user_headers
    )
    assert series.status_code == 200
    assert len(series.json()) == 45

    trend = client.get(
        f"/api/v1/analytics/datasets/{seeded_dataset}/trend", headers=user_headers
    )
    assert trend.status_code == 200
    assert trend.json()["direction"] == "up"


def test_flat_series_detects_flat_trend(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Flat", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    points = [{"timestamp": f"2026-01-{i+1:02d}T00:00:00Z", "value": 50.0} for i in range(20)]
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": points}
    )
    resp = client.get(f"/api/v1/analytics/datasets/{dataset_id}", headers=user_headers)
    assert resp.json()["trend"]["direction"] == "flat"
