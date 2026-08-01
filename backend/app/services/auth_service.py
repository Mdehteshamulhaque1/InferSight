"""Authentication and user services."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    SecurityError,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.models import RefreshToken, User


class DuplicateUserError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class TokenNotFoundError(Exception):
    pass


class TokenRevokedError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(
    db: Session, email: str, password: str, full_name: str, role: str = "analyst"
) -> User:
    email = email.lower().strip()
    if get_user_by_email(db, email) is not None:
        raise DuplicateUserError("a user with this email already exists")
    user = User(
        email=email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_admin(db: Session) -> User | None:
    """Idempotently create the bootstrap admin from settings."""
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        return None
    existing = get_user_by_email(db, settings.admin_email)
    if existing is not None:
        return existing
    return create_user(
        db,
        settings.admin_email,
        settings.admin_password,
        settings.admin_name,
        role="admin",
    )


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("invalid email or password")
    if not user.is_active:
        raise InvalidCredentialsError("account is disabled")
    return user


def issue_token_pair(db: Session, user: User, user_agent: str | None, ip: str | None):
    access_token, expires_in = create_access_token(str(user.id))
    raw_refresh, digest = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=refresh_expiry(),
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip,
        )
    )
    db.commit()
    return access_token, raw_refresh, expires_in


def _revoke(db: Session, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(timezone.utc)
    db.add(token)


def rotate_refresh_token(
    db: Session, raw_token: str, user_agent: str | None, ip: str | None
):
    """Validate a refresh token, revoke it, and issue a new token pair."""
    digest = hash_refresh_token(raw_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if stored is None:
        raise TokenNotFoundError("refresh token not found")
    if not stored.is_active_token:
        _revoke(db, stored)
        db.commit()
        raise TokenRevokedError("refresh token has expired or is revoked")
    user = get_user_by_id(db, stored.user_id)
    if user is None or not user.is_active:
        raise TokenRevokedError("user is no longer active")
    _revoke(db, stored)
    db.commit()
    return issue_token_pair(db, user, user_agent, ip)


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    digest = hash_refresh_token(raw_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if stored is not None:
        _revoke(db, stored)
        db.commit()


def revoke_all_user_tokens(db: Session, user_id: int) -> int:
    tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    count = 0
    for token in tokens:
        _revoke(db, token)
        count += 1
    db.commit()
    return count


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise SecurityError("current password is incorrect")
    user.hashed_password = hash_password(new)
    db.add(user)
    db.commit()
