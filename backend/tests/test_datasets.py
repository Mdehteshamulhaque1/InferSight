"""Dataset CRUD and metric-point ingestion tests."""

from __future__ import annotations

from tests.conftest import make_series


def test_create_dataset(client, user_headers):
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={
            "name": "Monthly Revenue",
            "slug": "monthly-revenue",
            "metric_type": "revenue",
            "unit": "USD",
            "currency": "usd",
            "granularity": "month",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "monthly-revenue"
    assert data["currency"] == "USD"
    assert data["point_count"] == 0


def test_create_dataset_generates_slug(client, user_headers):
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "My Awesome Dataset!", "metric_type": "custom", "granularity": "day"},
    )
    assert resp.status_code == 201
    assert resp.json()["slug"] == "my-awesome-dataset"


def test_duplicate_slug_conflict(client, user_headers):
    payload = {"name": "Revenue", "slug": "revenue", "metric_type": "revenue", "granularity": "day"}
    assert client.post("/api/v1/datasets", headers=user_headers, json=payload).status_code == 201
    resp = client.post("/api/v1/datasets", headers=user_headers, json=payload)
    assert resp.status_code == 409


def test_invalid_granularity_rejected(client, user_headers):
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Bad", "metric_type": "revenue", "granularity": "yearly"},
    )
    assert resp.status_code == 422


def test_list_datasets_paginated(client, user_headers):
    for i in range(5):
        client.post(
            "/api/v1/datasets",
            headers=user_headers,
            json={"name": f"Dataset {i}", "metric_type": "custom", "granularity": "day"},
        )
    resp = client.get("/api/v1/datasets", headers=user_headers, params={"limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["pages"] == 3


def test_get_update_delete_dataset(client, user_headers):
    created = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "To Edit", "metric_type": "custom", "granularity": "day"},
    ).json()

    resp = client.get(f"/api/v1/datasets/{created['id']}", headers=user_headers)
    assert resp.status_code == 200

    resp = client.patch(
        f"/api/v1/datasets/{created['id']}",
        headers=user_headers,
        json={"description": "updated description"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated description"

    resp = client.delete(f"/api/v1/datasets/{created['id']}", headers=user_headers)
    assert resp.status_code == 200
    assert client.get(f"/api/v1/datasets/{created['id']}", headers=user_headers).status_code == 404


def test_dataset_isolation_between_users(client, user_headers, admin_headers):
    created = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Private", "metric_type": "custom", "granularity": "day"},
    ).json()
    resp = client.get(f"/api/v1/datasets/{created['id']}", headers=admin_headers)
    assert resp.status_code == 404


def test_ingest_points_idempotent(client, user_headers, seeded_dataset):
    points = make_series(days=10)
    resp = client.post(
        f"/api/v1/datasets/{seeded_dataset}/points",
        headers=user_headers,
        json={"points": points},
    )
    assert resp.status_code == 200
    assert resp.json()["skipped_duplicates"] == 10
    assert resp.json()["inserted"] == 0


def test_list_points_with_filters(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/points",
        headers=user_headers,
        params={"start": "2026-01-10T00:00:00Z", "end": "2026-01-20T00:00:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 11


def test_points_order_desc(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/points",
        headers=user_headers,
        params={"order": "desc"},
    )
    items = resp.json()["items"]
    assert items[0]["timestamp"] > items[-1]["timestamp"]


def test_empty_dataset_analytics_fails(client, user_headers):
    dataset_id = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Empty", "metric_type": "custom", "granularity": "day"},
    ).json()["id"]
    resp = client.get(f"/api/v1/analytics/datasets/{dataset_id}", headers=user_headers)
    assert resp.status_code == 422
