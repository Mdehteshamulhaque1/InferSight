"""Auth API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession, rate_limit
from app.schemas.auth import PasswordChange, RefreshRequest, TokenPair, UserCreate, UserLogin, UserRead
from app.schemas.common import Message
from app.services import auth_service
from app.services.auth_service import (
    DuplicateUserError,
    InvalidCredentialsError,
    SecurityError,
    TokenNotFoundError,
    TokenRevokedError,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

LoginRateLimit = Annotated[None, Depends(rate_limit(max_requests=20, window_seconds=300))]
RegisterRateLimit = Annotated[None, Depends(rate_limit(max_requests=10, window_seconds=3600))]


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return user_agent, ip


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def register(
    payload: UserCreate, request: Request, db: DbSession, _: RegisterRateLimit
) -> TokenPair:
    try:
        user = auth_service.create_user(
            db, email=payload.email, password=payload.password, full_name=payload.full_name
        )
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    user_agent, ip = _client_context(request)
    access_token, refresh_token, expires_in = auth_service.issue_token_pair(
        db, user, user_agent, ip
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/login", response_model=TokenPair, summary="Authenticate and receive tokens")
def login(
    payload: UserLogin, request: Request, db: DbSession, _: LoginRateLimit
) -> TokenPair:
    try:
        user = auth_service.authenticate(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_agent, ip = _client_context(request)
    access_token, refresh_token, expires_in = auth_service.issue_token_pair(
        db, user, user_agent, ip
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenPair, summary="Rotate a refresh token")
def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenPair:
    user_agent, ip = _client_context(request)
    try:
        access_token, refresh_token, expires_in = auth_service.rotate_refresh_token(
            db, payload.refresh_token, user_agent, ip
        )
    except (TokenNotFoundError, TokenRevokedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/logout", response_model=Message, summary="Revoke the current refresh token")
def logout(payload: RefreshRequest, db: DbSession) -> Message:
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    return Message(detail="logged out")


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/change-password", response_model=Message, summary="Change account password")
def change_password(
    payload: PasswordChange, db: DbSession, user: CurrentUser
) -> Message:
    try:
        auth_service.change_password(db, user, payload.current_password, payload.new_password)
    except SecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    auth_service.revoke_all_user_tokens(db, user.id)
    return Message(detail="password updated; all sessions were signed out")


@router.post("/revoke-sessions", response_model=Message, summary="Sign out every device")
def revoke_sessions(db: DbSession, user: CurrentUser) -> Message:
    count = auth_service.revoke_all_user_tokens(db, user.id)
    return Message(detail=f"revoked {count} session(s)")
