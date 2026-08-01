"""Shared Pydantic schemas."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int


class Message(BaseModel):
    detail: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any | None = None
