"""Forecasting endpoint tests."""

from __future__ import annotations

from tests.conftest import make_series


def test_forecast_auto(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/forecasts/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"horizon": 14},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["horizon"] == 14
    assert len(data["points"]) == 14
    assert data["method"] in {"linear", "es", "holt"}
    assert data["metrics"]["holdout_points"] >= 2
    assert data["metrics"]["mae"] is not None
    for point in data["points"]:
        assert point["value"] > 0
        assert point["lower"] is not None
        assert point["upper"] is not None
        assert point["lower"] <= point["value"] <= point["upper"]


def test_forecast_confidence_interval_widens(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/forecasts/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"horizon": 30},
    )
    points = resp.json()["points"]
    spread_first = points[0]["upper"] - points[0]["lower"]
    spread_last = points[-1]["upper"] - points[-1]["lower"]
    assert spread_last >= spread_first


def test_forecast_horizon_validation(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/forecasts/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"horizon": 0},
    )
    assert resp.status_code == 422


def test_forecast_explicit_methods(client, user_headers, seeded_dataset):
    for method in ["linear", "es", "holt"]:
        resp = client.get(
            f"/api/v1/forecasts/datasets/{seeded_dataset}",
            headers=user_headers,
            params={"method": method},
        )
        assert resp.status_code == 200
        assert resp.json()["method"] == method


def test_forecast_invalid_method(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/forecasts/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"method": "magic"},
    )
    assert resp.status_code == 422


def test_forecast_trending_series_projects_upward(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Growth", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    points = make_series(days=60, base=100, step=5, seed=11)
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": points}
    )
    resp = client.get(
        f"/api/v1/forecasts/datasets/{dataset_id}",
        headers=user_headers,
        params={"method": "linear", "horizon": 10},
    )
    points_out = resp.json()["points"]
    assert points_out[-1]["value"] > points_out[0]["value"]
