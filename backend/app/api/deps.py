"""Shared FastAPI dependencies: DB session, current user, authorization."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import SecurityError, decode_access_token
from app.database.session import get_db
from app.models import User
from app.services.auth_service import get_user_by_id
from app.services.cache import cache_service

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except SecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = int(payload["sub"])
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account is disabled",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privileges required",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def rate_limit(max_requests: int, window_seconds: int):
    """Dependency factory enforcing a sliding-window rate limit per IP."""

    def limiter(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{client_ip}"
        raw = cache_service.get(key)
        count = int(raw) if raw is not None else 0
        if count >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded: {max_requests} requests per {window_seconds}s",
            )
        cache_service.set(key, str(count + 1), window_seconds)

    return limiter


def user_rate_limit(max_requests: int, window_seconds: int):
    """Dependency factory enforcing a sliding-window rate limit per user per
    endpoint path, so one heavy endpoint cannot exhaust another's budget."""

    def limiter(request: Request, user: CurrentUser) -> None:
        key = f"rl:u:{user.id}:{request.url.path}"
        raw = cache_service.get(key)
        count = int(raw) if raw is not None else 0
        if count >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded: {max_requests} requests per {window_seconds}s",
            )
        cache_service.set(key, str(count + 1), window_seconds)

    return limiter
