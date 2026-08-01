"""Insight generation and management tests."""

from __future__ import annotations


def test_generate_insight(client, user_headers, seeded_dataset):
    resp = client.post(
        f"/api/v1/insights/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"enrich_with_llm": False},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["kind"] == "insight"
    assert data["title"]
    assert data["body"]
    assert len(data["body"]) > 40
    assert data["payload"]["llm"] is False
    assert data["payload"]["anomaly_summary"]["total"] >= 0


def test_insight_title_mentions_dataset(client, user_headers, seeded_dataset):
    resp = client.post(
        f"/api/v1/insights/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"enrich_with_llm": False},
    )
    assert "Test Revenue" in resp.json()["title"]


def test_list_and_delete_insights(client, user_headers, seeded_dataset):
    client.post(
        f"/api/v1/insights/datasets/{seeded_dataset}",
        headers=user_headers,
        params={"enrich_with_llm": False},
    )
    resp = client.get("/api/v1/insights", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    insight_id = data["items"][0]["id"]

    resp = client.get("/api/v1/insights", headers=user_headers, params={"dataset_id": seeded_dataset})
    assert resp.json()["total"] == 1

    resp = client.delete(f"/api/v1/insights/{insight_id}", headers=user_headers)
    assert resp.status_code == 200
    assert client.get("/api/v1/insights", headers=user_headers).json()["total"] == 0


def test_insight_requires_data(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "No Data", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    resp = client.post(
        f"/api/v1/insights/datasets/{dataset_id}", headers=user_headers
    )
    assert resp.status_code == 422


def test_insight_isolation_between_users(client, user_headers, admin_headers):
    client.post(
        f"/api/v1/insights/datasets/{seeded_dataset_id(client, user_headers)}",
        headers=user_headers,
        params={"enrich_with_llm": False},
    )
    resp = client.get("/api/v1/insights", headers=admin_headers)
    assert resp.json()["total"] == 0


def seeded_dataset_id(client, headers):
    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        json={"name": "Isolation", "metric_type": "custom", "granularity": "day"},
    )
    dataset_id = resp.json()["id"]
    from tests.conftest import make_series

    client.post(
        f"/api/v1/datasets/{dataset_id}/points",
        headers=headers,
        json={"points": make_series(days=30)},
    )
    return dataset_id
