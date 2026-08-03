"""Tests for the Copilot upload-first flow: composite summary endpoint,
no-dataset file preview/auto-import, and per-user rate limiting."""

from __future__ import annotations

from tests.conftest import make_series


# --------------------------------------------------------------------------- #
# Composite summary endpoint (Copilot's one-call analysis)
# --------------------------------------------------------------------------- #
def test_summary_full_payload(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/summary", headers=user_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dataset_id"] == seeded_dataset
    assert data["name"] == "Test Revenue"
    assert data["currency"] == "USD"
    assert data["granularity"] == "day"
    assert len(data["kpis"]) >= 1
    assert {"direction", "slope_per_period_pct", "r_squared"} <= set(data["trend"])
    assert data["anomaly_count"] >= 0
    assert data["critical_anomalies"] >= 0
    assert data["health"]["score"] >= 0
    assert data["health"]["grade"] in ("A", "B", "C", "D", "F")
    assert data["forecast"]["method"] in ("auto", "linear", "naive", "seasonal", "es")
    assert len(data["forecast"]["points"]) > 0


def test_summary_requires_min_points(client, user_headers):
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={"name": "Empty", "metric_type": "custom", "granularity": "day"},
    )
    dataset_id = resp.json()["id"]
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/summary", headers=user_headers
    )
    assert resp.status_code == 422


def test_summary_is_cached_per_user(client, user_headers, admin_headers, seeded_dataset):
    url = f"/api/v1/datasets/{seeded_dataset}/summary"
    first = client.get(url, headers=user_headers).json()
    second = client.get(url, headers=user_headers).json()
    assert first == second

    other = client.get(url, headers=admin_headers)
    assert other.status_code == 404


# --------------------------------------------------------------------------- #
# Upload-first ingest (no dataset exists yet)
# --------------------------------------------------------------------------- #
def test_ingest_auto_creates_dataset(client, user_headers):
    csv_body = (
        "date,sales\n"
        "2026-02-01,100\n2026-02-02,120\n2026-02-03,110\n"
        "2026-02-04,140\n2026-02-05,135\n"
    ).encode()
    resp = client.post(
        "/api/v1/ingest/auto",
        headers=user_headers,
        files={"file": ("sales.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    dataset = body["dataset"]
    assert dataset["name"] == "Sales"
    assert body["result"]["inserted"] == 5
    assert body["result"]["point_count"] == 5

    # Dataset is immediately analyzable.
    summary = client.get(
        f"/api/v1/datasets/{dataset['id']}/summary", headers=user_headers
    )
    assert summary.status_code == 200, summary.text


def test_ingest_auto_rejects_bad_file(client, user_headers):
    resp = client.post(
        "/api/v1/ingest/auto",
        headers=user_headers,
        files={"file": ("data.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422


def test_ingest_auto_short_filename_gets_valid_name(client, user_headers):
    resp = client.post(
        "/api/v1/ingest/auto",
        headers=user_headers,
        files={"file": ("r.csv", b"date,value\n2026-01-01,1\n2026-01-02,2\n", "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["dataset"]["name"]) >= 2


def test_ingest_preview_no_dataset(client, user_headers):
    csv_body = b"date,value\n2026-01-01,1\n2026-01-02,2\n"
    resp = client.post(
        "/api/v1/ingest/preview",
        headers=user_headers,
        files={"file": ("preview.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["filename"] == "preview.csv"
    assert preview["timestamp_column"] == "date"
    assert preview["value_column"] == "value"
    assert preview["parsed_points"] == 2
    assert len(preview["sample"]) == 2


# --------------------------------------------------------------------------- #
# Per-user rate limiting
# --------------------------------------------------------------------------- #
def test_chat_user_rate_limit(client, user_headers, seeded_dataset):
    payload = {"dataset_id": seeded_dataset, "message": "how is my data doing"}
    for _ in range(30):
        resp = client.post("/api/v1/chat", headers=user_headers, json=payload)
        assert resp.status_code == 200, resp.text

    resp = client.post("/api/v1/chat", headers=user_headers, json=payload)
    assert resp.status_code == 429


def test_ingest_auto_user_rate_limit(client, user_headers):
    csv_body = b"date,value\n2026-01-01,1\n2026-01-02,2\n"
    files = {"file": ("r.csv", csv_body, "text/csv")}
    for _ in range(30):
        resp = client.post("/api/v1/ingest/auto", headers=user_headers, files=files)
        assert resp.status_code == 201, resp.text

    resp = client.post("/api/v1/ingest/auto", headers=user_headers, files=files)
    assert resp.status_code == 429
