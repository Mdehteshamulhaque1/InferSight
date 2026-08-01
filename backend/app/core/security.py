"""Security primitives: password hashing and JWT token handling.

Passwords are hashed with bcrypt. Access tokens are short-lived JWTs signed
with the configured secret; refresh tokens are opaque random strings whose
SHA-256 digest is persisted so they can be rotated and revoked server-side.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


class SecurityError(Exception):
    """Raised when token validation or credential verification fails."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str | int, expires_minutes: int | None = None) -> tuple[str, int]:
    settings = get_settings()
    minutes = expires_minutes or settings.access_token_expire_minutes
    expires_at = _now() + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": _now(),
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate an access token and return its payload."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise SecurityError("access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise SecurityError("invalid access token") from exc

    if payload.get("type") != "access":
        raise SecurityError("token is not an access token")
    return payload


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_digest) for a new refresh token."""
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_expiry(days: int | None = None) -> datetime:
    settings = get_settings()
    return _now() + timedelta(days=days or settings.refresh_token_expire_days)
