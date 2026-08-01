"""Authentication and token lifecycle tests."""

from __future__ import annotations


def test_health_and_root(client):
    assert client.get("/health").json() == {"status": "healthy", "version": "1.0.0"}
    assert client.get("/").status_code == 200


def test_register_returns_token_pair(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "new@test.dev", "password": "Password123", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@test.dev", "password": "Password123", "full_name": "Dup"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_register_rejects_weak_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@test.dev", "password": "short", "full_name": "Weak"},
    )
    assert resp.status_code == 422


def test_login_success_and_wrong_password(client, user_headers):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "Password123"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "WrongPass1"},
    )
    assert resp.status_code == 401


def test_refresh_token_rotation(client, user_headers):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "Password123"},
    )
    refresh = login.json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_refresh = resp.json()["refresh_token"]
    assert new_refresh != refresh

    # Old token must be rejected after rotation.
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(client, user_headers):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "Password123"},
    )
    refresh = login.json()["refresh_token"]

    assert client.post("/api/v1/auth/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_me_endpoint(client, user_headers):
    resp = client.get("/api/v1/auth/me", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "analyst@test.dev"
    assert resp.json()["role"] == "analyst"


def test_protected_route_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_protected_route_with_invalid_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


def test_change_password_revokes_sessions(client, user_headers):
    resp = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": "Password123", "new_password": "NewPassword456"},
    )
    assert resp.status_code == 200
    # Old password no longer works.
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "Password123"},
    )
    assert resp.status_code == 401
    # New password works.
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "NewPassword456"},
    )
    assert resp.status_code == 200


def test_login_rate_limit(client, user_headers):
    for _ in range(20):
        client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@test.dev", "password": "Password123"},
        )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@test.dev", "password": "Password123"},
    )
    assert resp.status_code == 429
