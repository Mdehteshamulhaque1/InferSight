"""Time handling helpers for bucketing and formatting."""

from __future__ import annotations

from datetime import datetime, timezone


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def bucket_key(dt: datetime, granularity: str) -> datetime:
    """Normalize a timestamp into a granularity bucket start."""
    dt = to_utc(dt)
    if granularity == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if granularity == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start - __import__("datetime").timedelta(days=start.weekday())
    if granularity == "month":
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def add_period(dt: datetime, granularity: str, periods: int = 1) -> datetime:
    dt = to_utc(dt)
    if granularity == "hour":
        return dt + __import__("datetime").timedelta(hours=periods)
    if granularity == "day":
        return dt + __import__("datetime").timedelta(days=periods)
    if granularity == "week":
        return dt + __import__("datetime").timedelta(weeks=periods)
    if granularity == "month":
        year = dt.year + (dt.month - 1 + periods) // 12
        month = (dt.month - 1 + periods) % 12 + 1
        return dt.replace(year=year, month=month)
    return dt + __import__("datetime").timedelta(days=periods)
