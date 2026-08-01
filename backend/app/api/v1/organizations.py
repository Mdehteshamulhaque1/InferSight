"""Organization and membership API routes (RBAC)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _load_org(db: DbSession, org_id: int, user) -> tuple[object, object]:
    try:
        org = organization_service.get_organization(db, org_id, user)
        member = organization_service.membership_for(db, org, user)
    except organization_service.OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return org, member


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create an organization")
def create_organization(
    payload: dict, db: DbSession, user: CurrentUser
) -> dict:
    name = (payload.get("name") or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="name is required")
    org = organization_service.create_organization(
        db, user, name, member_emails=payload.get("member_emails")
    )
    return {"id": org.id, "name": org.name, "slug": org.slug, "role": "owner"}


@router.get("", summary="List my organizations")
def list_organizations(db: DbSession, user: CurrentUser) -> list[dict]:
    return [
        {
            "id": item["organization"].id,
            "name": item["organization"].name,
            "slug": item["organization"].slug,
            "role": item["role"],
        }
        for item in organization_service.list_organizations(db, user)
    ]


@router.get("/{org_id}", summary="Organization detail with members")
def get_organization(org_id: int, db: DbSession, user: CurrentUser) -> dict:
    org, member = _load_org(db, org_id, user)
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "role": member.role,
        "members": organization_service.members_of(db, org),
    }


@router.post(
    "/{org_id}/members", status_code=status.HTTP_201_CREATED, summary="Add a member"
)
def add_member(org_id: int, payload: dict, db: DbSession, user: CurrentUser) -> dict:
    org, member = _load_org(db, org_id, user)
    try:
        return organization_service.add_member(
            db, org, member, payload.get("email", ""), payload.get("role", "analyst")
        )
    except organization_service.OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch(
    "/{org_id}/members/{member_user_id}", summary="Change a member's role"
)
def update_member_role(
    org_id: int, member_user_id: int, payload: dict, db: DbSession, user: CurrentUser
) -> dict:
    org, member = _load_org(db, org_id, user)
    try:
        return organization_service.update_member_role(
            db, org, member, member_user_id, payload.get("role", "analyst")
        )
    except organization_service.OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete("/{org_id}/members/{member_user_id}", response_model=Message, summary="Remove a member")
def remove_member(
    org_id: int, member_user_id: int, db: DbSession, user: CurrentUser
) -> Message:
    org, member = _load_org(db, org_id, user)
    try:
        organization_service.remove_member(db, org, member, member_user_id)
    except organization_service.OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Message(detail="member removed")


@router.post("/{org_id}/transfer/{member_user_id}", response_model=Message, summary="Transfer ownership")
def transfer_ownership(
    org_id: int, member_user_id: int, db: DbSession, user: CurrentUser
) -> Message:
    org, member = _load_org(db, org_id, user)
    try:
        organization_service.transfer_ownership(db, org, member, member_user_id)
    except organization_service.OrganizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return Message(detail="ownership transferred")
