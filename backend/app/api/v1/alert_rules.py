"""Alert rule and alert delivery routes.

Rules are scoped to a dataset: creation and mutation require write access to
the dataset, and listing only surfaces rules on datasets the caller can read.
Delivery history is scoped to the alert's owner.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.alert_rules import (
    AlertDeliveryOut,
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
)
from app.schemas.common import Message, Paginated
from app.services import alert_service, dataset_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError
from app.services.rbac_service import can_read_dataset

router = APIRouter(prefix="/alert-rules", tags=["Alert Rules"])
deliveries_router = APIRouter(prefix="/alerts", tags=["Alert Rules"])


def _load_dataset(db: DbSession, dataset_id: int, user: CurrentUser):
    try:
        return dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _load_rule(db: DbSession, rule_id: int):
    try:
        return alert_service.get_rule(db, rule_id)
    except alert_service.AlertRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _require_rule_write(db: DbSession, rule, user: CurrentUser) -> None:
    if rule.dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")
    try:
        dataset_service.require_write_access(db, rule.dataset, user)
    except DatasetAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AlertRuleOut,
    summary="Create an alert rule",
)
def create_alert_rule(
    payload: AlertRuleCreate, db: DbSession, user: CurrentUser
) -> AlertRuleOut:
    dataset = _load_dataset(db, payload.dataset_id, user)
    try:
        dataset_service.require_write_access(db, dataset, user)
    except DatasetAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AlertRuleOut.model_validate(
        alert_service.create_rule(db, dataset.id, payload)
    )


@router.get(
    "",
    response_model=Paginated[AlertRuleOut],
    summary="List alert rules",
)
def list_alert_rules(
    db: DbSession,
    user: CurrentUser,
    dataset_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    if dataset_id is not None:
        _load_dataset(db, dataset_id, user)
    rules = alert_service.list_rules(db, dataset_id=dataset_id)
    visible = [rule for rule in rules if can_read_dataset(db, rule.dataset, user)]
    offset = (page - 1) * limit
    items = visible[offset : offset + limit]
    total = len(visible)
    return {
        "items": [AlertRuleOut.model_validate(rule) for rule in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }


@router.patch(
    "/{rule_id}",
    response_model=AlertRuleOut,
    summary="Update an alert rule",
)
def update_alert_rule(
    rule_id: int, payload: AlertRuleUpdate, db: DbSession, user: CurrentUser
) -> AlertRuleOut:
    rule = _load_rule(db, rule_id)
    _require_rule_write(db, rule, user)
    return AlertRuleOut.model_validate(alert_service.update_rule(db, rule, payload))


@router.delete(
    "/{rule_id}",
    response_model=Message,
    summary="Delete an alert rule",
)
def delete_alert_rule(rule_id: int, db: DbSession, user: CurrentUser) -> Message:
    rule = _load_rule(db, rule_id)
    _require_rule_write(db, rule, user)
    alert_service.delete_rule(db, rule)
    return Message(detail="alert rule deleted")


@deliveries_router.get(
    "/{alert_id}/deliveries",
    response_model=Paginated[AlertDeliveryOut],
    summary="Delivery history for an alert",
)
def list_alert_deliveries(
    alert_id: int,
    db: DbSession,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    try:
        deliveries = alert_service.list_deliveries_for_alert(db, user, alert_id)
    except alert_service.AlertNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except alert_service.AlertAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    offset = (page - 1) * limit
    items = deliveries[offset : offset + limit]
    total = len(deliveries)
    return {
        "items": [AlertDeliveryOut.model_validate(d) for d in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit else 0,
    }
