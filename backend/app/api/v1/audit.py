"""Audit trail API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Paginated
from app.schemas.intelligence import AuditEventOut
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=Paginated[AuditEventOut], summary="Audit trail")
def list_audit(
    db: DbSession,
    user: CurrentUser,
    resource_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    events = audit_service.list_events(
        db, user, limit=limit * page, resource_id=resource_id
    )
    offset = (page - 1) * limit
    items = events[offset : offset + limit]
    total = len(events)
    return {
        "items": [AuditEventOut.model_validate(e) for e in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }
