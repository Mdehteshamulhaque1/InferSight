"""Role-based access control for organizations and datasets.

Roles (strongest to weakest): owner > admin > manager > analyst.
- owner: creator of the organization; full control including membership.
- admin: manage members and datasets.
- manager: read/write datasets.
- analyst: read-only.

A dataset is visible to its owner or to any member of its organization.
Mutations additionally require an org role of manager or higher.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.organization import Organization, OrganizationMember
from app.models.user import User

ROLE_ORDER = {"analyst": 0, "manager": 1, "admin": 2, "owner": 3}
WRITE_ROLES = {"owner", "admin", "manager"}


class RbacError(Exception):
    pass


def organization_for_user(db: Session, user: User) -> Organization | None:
    member = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    if member is None:
        return None
    return db.get(Organization, member.organization_id)


def user_membership(db: Session, user: User, org_id: int) -> OrganizationMember | None:
    return db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org_id,
        )
    )


def can_read_dataset(db: Session, dataset: Dataset, user: User) -> bool:
    if dataset.owner_id == user.id:
        return True
    if dataset.organization_id is not None:
        return user_membership(db, user, dataset.organization_id) is not None
    return False


def can_write_dataset(db: Session, dataset: Dataset, user: User) -> bool:
    if dataset.owner_id == user.id:
        return True
    if dataset.organization_id is not None:
        member = user_membership(db, user, dataset.organization_id)
        return member is not None and member.role in WRITE_ROLES
    return False


def dataset_read_scope(db: Session, user: User):
    """SQLAlchemy predicate restricting a query to datasets the user can read."""
    org_ids = db.scalars(
        select(OrganizationMember.organization_id).where(
            OrganizationMember.user_id == user.id
        )
    ).all()
    from sqlalchemy import or_

    return or_(
        Dataset.owner_id == user.id,
        Dataset.organization_id.in_(list(org_ids)) if org_ids else False,
    )
