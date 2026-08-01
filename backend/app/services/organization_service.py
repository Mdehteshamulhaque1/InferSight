"""Organization + membership services (RBAC)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services.auth_service import get_user_by_email
from app.services.rbac_service import ROLE_ORDER, WRITE_ROLES

ROLES = ("owner", "admin", "manager", "analyst")


class OrganizationError(Exception):
    pass


class OrganizationNotFoundError(OrganizationError):
    pass


class OrganizationAccessError(OrganizationError):
    pass


class MembershipError(OrganizationError):
    pass


def _slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9-_]+", "-", slug).strip("-")
    return slug or "organization"


def create_organization(
    db: Session, user: User, name: str, member_emails: list[str] | None = None
) -> Organization:
    org = Organization(name=name.strip(), slug=_slugify(name), created_by=user.id)
    db.add(org)
    db.flush()
    db.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    )
    for email in member_emails or []:
        invitee = get_user_by_email(db, email.strip())
        if invitee is not None and invitee.id != user.id:
            db.add(
                OrganizationMember(
                    organization_id=org.id, user_id=invitee.id, role="analyst"
                )
            )
    db.commit()
    db.refresh(org)
    return org


def get_organization(db: Session, org_id: int, user: User) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise OrganizationNotFoundError("organization not found")
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if member is None:
        raise OrganizationAccessError("you are not a member of this organization")
    return org


def membership_for(
    db: Session, org: Organization, user: User
) -> OrganizationMember | None:
    return db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
        )
    )


def require_role(member: OrganizationMember, minimum: str) -> None:
    if member is None or ROLE_ORDER.get(member.role, -1) < ROLE_ORDER.get(minimum, 99):
        raise OrganizationAccessError(
            f"this action requires the '{minimum}' role or higher"
        )


def list_organizations(db: Session, user: User) -> list[Organization]:
    memberships = db.scalars(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    ).all()
    orgs = []
    for m in memberships:
        org = db.get(Organization, m.organization_id)
        if org is not None:
            orgs.append({"organization": org, "role": m.role})
    return orgs


def members_of(db: Session, org: Organization) -> list[dict]:
    members = db.scalars(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.role.asc())
    ).all()
    out = []
    for m in members:
        member_user = db.get(User, m.user_id)
        if member_user is None:
            continue
        out.append(
            {
                "user_id": member_user.id,
                "email": member_user.email,
                "full_name": member_user.full_name,
                "role": m.role,
            }
        )
    return out


def add_member(
    db: Session, org: Organization, actor: OrganizationMember, email: str, role: str
) -> dict:
    if role not in ROLES:
        raise MembershipError(f"role must be one of {ROLES}")
    if role == "owner":
        raise MembershipError("use transfer_ownership to grant the owner role")
    require_role(actor, "admin")
    invitee = get_user_by_email(db, email.strip())
    if invitee is None:
        raise MembershipError("no user with this email exists")
    existing = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == invitee.id,
        )
    )
    if existing is not None:
        raise MembershipError("this user is already a member")
    db.add(
        OrganizationMember(
            organization_id=org.id, user_id=invitee.id, role=role
        )
    )
    db.commit()
    return {"user_id": invitee.id, "email": invitee.email, "full_name": invitee.full_name, "role": role}


def update_member_role(
    db: Session, org: Organization, actor: OrganizationMember, user_id: int, role: str
) -> dict:
    if role not in ROLES:
        raise MembershipError(f"role must be one of {ROLES}")
    if role == "owner":
        raise MembershipError("use transfer_ownership to grant the owner role")
    require_role(actor, "admin")
    target = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user_id,
        )
    )
    if target is None:
        raise MembershipError("user is not a member of this organization")
    if target.role == "owner":
        raise MembershipError("cannot change the owner's role")
    target.role = role
    db.commit()
    user = db.get(User, user_id)
    return {
        "user_id": user_id,
        "email": user.email if user else "",
        "full_name": user.full_name if user else "",
        "role": role,
    }


def remove_member(
    db: Session, org: Organization, actor: OrganizationMember, user_id: int
) -> None:
    require_role(actor, "admin")
    target = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user_id,
        )
    )
    if target is None:
        raise MembershipError("user is not a member of this organization")
    if target.role == "owner":
        raise MembershipError("cannot remove the owner")
    db.delete(target)
    db.commit()


def transfer_ownership(
    db: Session, org: Organization, actor: OrganizationMember, user_id: int
) -> None:
    require_role(actor, "owner")
    target = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user_id,
        )
    )
    if target is None:
        raise MembershipError("user is not a member of this organization")
    actor.role = "admin"
    target.role = "owner"
    db.commit()
