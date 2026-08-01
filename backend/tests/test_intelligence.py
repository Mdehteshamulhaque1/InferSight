"""Tests for intelligence features: profiling, KPI discovery, root-cause,
recommendations, health score, chat, alerts, versioning, audit, ingestion, and
organization RBAC."""

from __future__ import annotations

from tests.conftest import make_series


def _dataset_id(client, headers, **overrides):
    payload = {
        "name": "Intelligence",
        "metric_type": "custom",
        "granularity": "day",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/datasets", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_spiky(client, headers):
    dataset_id = _dataset_id(client, headers)
    points = make_series(days=60, base=100, step=1)
    points[40]["value"] = 1000
    points[45]["value"] = 10
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=headers, json={"points": points}
    )
    return dataset_id


# --------------------------------------------------------------------------- #
# Profiling & KPI discovery
# --------------------------------------------------------------------------- #
def test_profile_endpoint(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/profile", headers=user_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 45
    assert {"min", "max", "mean", "median", "std", "sum", "cv"} <= set(data["stats"])
    assert data["trend"]["direction"] in ("up", "down", "flat")
    assert data["quality"]["completeness_pct"] > 0
    assert len(data["top_points"]) == 5
    assert len(data["biggest_movers"]) >= 1


def test_profile_requires_points(client, user_headers):
    dataset_id = _dataset_id(client, user_headers)
    resp = client.get(f"/api/v1/datasets/{dataset_id}/profile", headers=user_headers)
    assert resp.status_code == 422


def test_kpi_discovery(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/kpis/discover", headers=user_headers
    )
    assert resp.status_code == 200
    kpis = resp.json()
    keys = {k["key"] for k in kpis}
    assert {"total", "average", "latest", "peak", "trough", "growth"} <= keys
    latest = next(k for k in kpis if k["key"] == "latest")
    assert "change_pct" in latest


# --------------------------------------------------------------------------- #
# Recommendations & health
# --------------------------------------------------------------------------- #
def test_recommendations(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/recommendations", headers=user_headers
    )
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) >= 1
    for rec in recs:
        assert rec["severity"] in ("critical", "warning", "info")
        assert rec["action"] and rec["rationale"] and rec["impact"]


def test_recommendations_flag_spikes(client, user_headers):
    dataset_id = _seed_spiky(client, user_headers)
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/recommendations", headers=user_headers
    )
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert "rec-critical-anomaly" in ids


def test_health_score(client, user_headers, seeded_dataset):
    resp = client.get(f"/api/v1/datasets/{seeded_dataset}/health", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score"] <= 100
    assert data["grade"] in ("A", "B", "C", "D", "F")
    assert data["verdict"]
    weight_sum = sum(c["weight"] for c in data["components"])
    assert abs(weight_sum - 1.0) < 1e-9


# --------------------------------------------------------------------------- #
# Root-cause analysis
# --------------------------------------------------------------------------- #
def test_root_cause(client, user_headers):
    dataset_id = _seed_spiky(client, user_headers)
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/root-cause", headers=user_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["direction"] in ("spike", "drop")
    assert data["delta_pct"] != 0
    assert data["hypotheses"]
    assert data["time_effects"]
    # The biggest spike (1000) should be selected as most severe.
    assert data["actual"] >= 900


def test_root_cause_clean_series_returns_422(client, user_headers):
    from datetime import datetime, timedelta, timezone

    dataset_id = _dataset_id(client, user_headers)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    flat = [
        {
            "timestamp": (start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "value": 100.0,
        }
        for i in range(40)
    ]
    client.post(
        f"/api/v1/datasets/{dataset_id}/points", headers=user_headers, json={"points": flat}
    )
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/root-cause", headers=user_headers
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def test_chat_trend(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/chat",
        headers=user_headers,
        json={"message": "What is the trend?", "dataset_id": seeded_dataset},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "trend"
    assert data["reply"]
    assert data["data"]["profile"]["trend"]["direction"] in ("up", "down", "flat")
    assert len(data["followups"]) >= 1


def test_chat_defaults_to_first_dataset(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/chat", headers=user_headers, json={"message": "hi"}
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "greeting"


def test_chat_anomaly_intent(client, user_headers):
    dataset_id = _seed_spiky(client, user_headers)
    resp = client.post(
        "/api/v1/chat",
        headers=user_headers,
        json={"message": "show me anomalies", "dataset_id": dataset_id},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "anomaly"


def test_chat_requires_message(client, user_headers, seeded_dataset):
    resp = client.post(
        "/api/v1/chat", headers=user_headers, json={"message": "  "}
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
def test_alerts_sync_list_read(client, user_headers):
    dataset_id = _seed_spiky(client, user_headers)
    resp = client.post(f"/api/v1/alerts/sync/{dataset_id}", headers=user_headers)
    assert resp.status_code == 201, resp.text
    sync = resp.json()
    assert sync["critical"] >= 2
    assert sync["alerts_created"] >= 2

    resp = client.get("/api/v1/alerts", headers=user_headers)
    assert resp.status_code == 200
    alerts = resp.json()["items"]
    assert len(alerts) >= 2
    unread = {a["is_read"] for a in alerts}
    assert unread == {False}

    resp = client.get("/api/v1/alerts/unread-count", headers=user_headers)
    assert resp.json()["count"] >= 2

    first_id = alerts[0]["id"]
    resp = client.post(f"/api/v1/alerts/{first_id}/read", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    resp = client.post("/api/v1/alerts/read-all", headers=user_headers)
    assert resp.status_code == 200
    resp = client.get("/api/v1/alerts/unread-count", headers=user_headers)
    assert resp.json()["count"] == 0


def test_alerts_are_deduplicated(client, user_headers):
    dataset_id = _seed_spiky(client, user_headers)
    client.post(f"/api/v1/alerts/sync/{dataset_id}", headers=user_headers)
    client.post(f"/api/v1/alerts/sync/{dataset_id}", headers=user_headers)
    resp = client.get("/api/v1/alerts", headers=user_headers)
    titles = {a["title"] for a in resp.json()["items"]}
    assert len(titles) == len(resp.json()["items"])


# --------------------------------------------------------------------------- #
# Versioning & audit
# --------------------------------------------------------------------------- #
def test_versioning_and_rollback(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/versions", headers=user_headers
    )
    assert resp.status_code == 200
    versions = resp.json()["items"]
    assert len(versions) >= 1
    first_version = versions[-1]["version_no"]

    # Ingest more points -> a new version.
    extra = make_series(start="2026-02-15", days=5, base=300, step=1, seed=2)
    client.post(
        f"/api/v1/datasets/{seeded_dataset}/points",
        headers=user_headers,
        json={"points": extra},
    )
    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/versions", headers=user_headers
    )
    assert resp.json()["items"][0]["total_after"] == 50

    resp = client.post(
        f"/api/v1/datasets/{seeded_dataset}/versions/{first_version}/rollback",
        headers=user_headers,
    )
    assert resp.status_code == 200, resp.text
    assert "restored to version" in resp.json()["detail"]

    resp = client.get(
        f"/api/v1/datasets/{seeded_dataset}/points",
        headers=user_headers,
        params={"limit": 5000},
    )
    assert resp.json()["total"] == 45


def test_audit_trail(client, user_headers, seeded_dataset):
    resp = client.get("/api/v1/audit", headers=user_headers)
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()["items"]}
    assert "dataset.create" in actions
    assert "points.ingest" in actions


def test_audit_filter_by_resource(client, user_headers, seeded_dataset):
    resp = client.get(
        "/api/v1/audit", headers=user_headers, params={"resource_id": seeded_dataset}
    )
    assert resp.status_code == 200
    for event in resp.json()["items"]:
        assert event["resource_id"] == seeded_dataset


# --------------------------------------------------------------------------- #
# File ingestion
# --------------------------------------------------------------------------- #
def test_ingest_csv_preview_and_commit(client, user_headers):
    dataset_id = _dataset_id(client, user_headers)
    csv_body = (
        "date,revenue\n"
        "2026-01-01,100\n2026-01-02,120\n2026-01-03,110\n"
        "2026-01-04,$1,000\n2026-01-05,140\n"
    ).encode()
    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/preview",
        headers=user_headers,
        files={"file": ("revenue.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["parsed_points"] == 5
    assert preview["value_column"] == "revenue"
    assert preview["detected_granularity"] == "day"

    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/file",
        headers=user_headers,
        files={"file": ("revenue.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()
    assert result["inserted"] == 5
    assert result["parsed_points"] == 5
    assert result["point_count"] == 5

    # Idempotent re-import skips duplicates.
    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/file",
        headers=user_headers,
        files={"file": ("revenue.csv", csv_body, "text/csv")},
    )
    assert resp.json()["inserted"] == 0
    assert resp.json()["skipped_duplicates"] == 5


def test_ingest_csv_replace(client, user_headers):
    dataset_id = _dataset_id(client, user_headers)
    client.post(
        f"/api/v1/datasets/{dataset_id}/points",
        headers=user_headers,
        json={"points": make_series(days=30)},
    )
    csv_body = b"date,value\n2026-03-01,10\n2026-03-02,20\n"
    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/file",
        headers=user_headers,
        params={"replace": "true"},
        files={"file": ("small.csv", csv_body, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["replaced"] is True
    assert resp.json()["point_count"] == 2


def test_ingest_json_map(client, user_headers):
    dataset_id = _dataset_id(client, user_headers)
    body = b'{"2026-01-01": 1, "2026-01-02": 2, "2026-01-03": 3}'
    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/file",
        headers=user_headers,
        files={"file": ("data.json", body, "application/json")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["inserted"] == 3


def test_ingest_unsupported_format(client, user_headers):
    dataset_id = _dataset_id(client, user_headers)
    resp = client.post(
        f"/api/v1/ingest/{dataset_id}/file",
        headers=user_headers,
        files={"file": ("data.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Organization RBAC
# --------------------------------------------------------------------------- #
def test_organization_lifecycle_and_dataset_sharing(client, user_headers):
    # Create an org as the analyst (owner).
    resp = client.post(
        "/api/v1/organizations",
        headers=user_headers,
        json={"name": "Acme Analytics"},
    )
    assert resp.status_code == 201, resp.text
    org_id = resp.json()["id"]
    assert resp.json()["role"] == "owner"

    resp = client.get("/api/v1/organizations", headers=user_headers)
    assert [o["id"] for o in resp.json()] == [org_id]

    # Register a second user to share with.
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "peer@test.dev",
            "password": "Password123",
            "full_name": "Peer Analyst",
        },
    )
    assert resp.status_code == 201
    peer_headers = {
        "Authorization": f"Bearer {resp.json()['access_token']}"
    }

    # Owner adds the peer as analyst.
    resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=user_headers,
        json={"email": "peer@test.dev", "role": "analyst"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "analyst"

    # Owner attaches a dataset to the org.
    resp = client.post(
        "/api/v1/datasets",
        headers=user_headers,
        json={
            "name": "Org Revenue",
            "metric_type": "revenue",
            "granularity": "day",
            "organization_id": org_id,
        },
    )
    assert resp.status_code == 201, resp.text
    dataset_id = resp.json()["id"]

    # Peer (analyst) can READ the shared dataset...
    resp = client.get(f"/api/v1/datasets/{dataset_id}", headers=peer_headers)
    assert resp.status_code == 200

    # ...but cannot WRITE it (analyst is read-only).
    resp = client.delete(f"/api/v1/datasets/{dataset_id}", headers=peer_headers)
    assert resp.status_code == 404

    # Peer appears in org detail.
    resp = client.get(f"/api/v1/organizations/{org_id}", headers=user_headers)
    member_emails = {m["email"] for m in resp.json()["members"]}
    assert "peer@test.dev" in member_emails
    assert resp.json()["role"] == "owner"


def test_organization_role_enforcement(client, user_headers):
    resp = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Strict Org"}
    )
    org_id = resp.json()["id"]

    # Register an analyst member.
    client.post(
        "/api/v1/auth/register",
        json={"email": "low@test.dev", "password": "Password123", "full_name": "Low"},
    )
    resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=user_headers,
        json={"email": "low@test.dev", "role": "analyst"},
    )
    assert resp.status_code == 201
    low_headers = {
        "Authorization": "Bearer "
        + client.post(
            "/api/v1/auth/login",
            json={"email": "low@test.dev", "password": "Password123"},
        ).json()["access_token"]
    }

    # Analyst cannot add members.
    resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=low_headers,
        json={"email": "nobody@test.dev", "role": "analyst"},
    )
    assert resp.status_code == 403

    # Analyst cannot attach a dataset to the org (needs manager+).
    resp = client.post(
        "/api/v1/datasets",
        headers=low_headers,
        json={"name": "Nope", "granularity": "day", "organization_id": org_id},
    )
    assert resp.status_code == 403

    # Non-member cannot read org detail.
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "outsider@test.dev", "password": "Password123", "full_name": "Out"},
    )
    outsider_headers = {
        "Authorization": f"Bearer {resp.json()['access_token']}"
    }
    resp = client.get(f"/api/v1/organizations/{org_id}", headers=outsider_headers)
    assert resp.status_code == 404


def test_organization_member_role_change(client, user_headers):
    resp = client.post(
        "/api/v1/organizations", headers=user_headers, json={"name": "Role Org"}
    )
    org_id = resp.json()["id"]
    client.post(
        "/api/v1/auth/register",
        json={"email": "mgr@test.dev", "password": "Password123", "full_name": "Mgr"},
    )
    client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers=user_headers,
        json={"email": "mgr@test.dev", "role": "analyst"},
    )
    mgr_headers = {
        "Authorization": "Bearer "
        + client.post(
            "/api/v1/auth/login",
            json={"email": "mgr@test.dev", "password": "Password123"},
        ).json()["access_token"]
    }
    mgr_id = client.get("/api/v1/auth/me", headers=mgr_headers).json()["id"]

    resp = client.patch(
        f"/api/v1/organizations/{org_id}/members/{mgr_id}",
        headers=user_headers,
        json={"role": "manager"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "manager"

    # Owner can remove the member.
    resp = client.delete(
        f"/api/v1/organizations/{org_id}/members/{mgr_id}", headers=user_headers
    )
    assert resp.status_code == 200
