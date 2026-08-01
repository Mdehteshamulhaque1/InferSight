"""Analytics engine: KPI computation, time-series resampling, and trend analysis.

All computation is pure Python (deterministic, dependency-free) so the
analytics layer is trivial to unit test and trivially portable.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, MetricPoint
from app.schemas.analytics import Kpi, SeriesPoint, Trend
from app.utils.time import bucket_key, to_utc

_GRAN_SECONDS = {"hour": 3600, "day": 86400, "week": 604800, "month": 2629800}
# Correlation window (in periods) around the anomaly timestamp, per granularity.
_CORRELATION_WINDOW_PERIODS = {"hour": 24, "day": 10, "week": 8, "month": 6}
_CORRELATION_MIN_OVERLAP = 5
_CORRELATION_THRESHOLD = 0.6
_CORRELATION_MAX_RESULTS = 5


def resample(points: list[object], granularity: str) -> list[SeriesPoint]:
    """Aggregate raw points into granularity buckets (sum per bucket)."""
    buckets: dict[datetime, float] = defaultdict(float)
    for point in points:
        key = bucket_key(point.timestamp, granularity)
        buckets[key] += point.value
    return [
        SeriesPoint(timestamp=ts, value=round(value, 6))
        for ts, value in sorted(buckets.items())
    ]


def linear_trend(points: list[object]) -> Trend:
    """Ordinary least-squares fit of value against time index."""
    n = len(points)
    if n < 2:
        return Trend(
            slope=0.0,
            intercept=points[0].value if n == 1 else 0.0,
            r_squared=1.0,
            direction="flat",
            fitted=resample(points, "day"),
        )
    xs = list(range(n))
    ys = [p.value for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    s_xx = sum((x - mean_x) ** 2 for x in xs)
    s_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = s_xy / s_xx if s_xx else 0.0
    intercept = mean_y - slope * mean_x

    if s_xx == 0:
        r_squared = 1.0
    else:
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0

    # A slope is only "meaningful" when it exceeds 0.5% of the series mean per
    # period; anything smaller is treated as a flat series.
    threshold = (abs(mean_y) * 0.005) if mean_y else 1e-12
    direction = "up" if slope > threshold else "down" if slope < -threshold else "flat"

    fitted = [
        SeriesPoint(timestamp=p.timestamp, value=round(intercept + slope * i, 6))
        for i, p in enumerate(points)
    ]
    return Trend(
        slope=round(slope, 6),
        intercept=round(intercept, 6),
        r_squared=round(r_squared, 6),
        direction=direction,
        fitted=fitted,
    )


def _pct_change(current: float, previous: float) -> float | None:
    if previous is None or previous == 0:
        return None
    return round(((current - previous) / previous) * 100.0, 2)


def compute_kpis(series: list[SeriesPoint]) -> list[Kpi]:
    """Compute KPI cards over a resampled series."""
    if not series:
        return []
    values = [s.value for s in series]
    total = sum(values)
    average = total / len(values)
    latest = values[-1]
    previous = values[-2] if len(values) >= 2 else None
    peak_index = max(range(len(values)), key=values.__getitem__)
    trough_index = min(range(len(values)), key=values.__getitem__)

    growth_rates = []
    for a, b in zip(values[:-1], values[1:]):
        if a != 0:
            growth_rates.append((b - a) / abs(a) * 100.0)
    growth = sum(growth_rates) / len(growth_rates) if growth_rates else None

    kpis = [
        Kpi(key="total", label="Total", value=round(total, 6), change_pct=None),
        Kpi(key="average", label="Average", value=round(average, 6), change_pct=None),
        Kpi(
            key="latest",
            label="Latest",
            value=round(latest, 6),
            change_pct=_pct_change(latest, previous),
            metadata={"timestamp": series[-1].timestamp},
        ),
        Kpi(
            key="peak",
            label="Peak",
            value=round(values[peak_index], 6),
            metadata={"timestamp": series[peak_index].timestamp},
        ),
        Kpi(
            key="trough",
            label="Trough",
            value=round(values[trough_index], 6),
            metadata={"timestamp": series[trough_index].timestamp},
        ),
        Kpi(
            key="growth",
            label="Growth (period avg)",
            value=round(growth, 6) if growth is not None else 0.0,
            change_pct=None,
            metadata={"samples": len(growth_rates)},
        ),
    ]
    return kpis


def describe_change(change_pct: float | None) -> str | None:
    if change_pct is None:
        return None
    if change_pct > 0:
        return f"up {change_pct:.1f}%"
    if change_pct < 0:
        return f"down {abs(change_pct):.1f}%"
    return "flat"


def fmt_amount(value: float, currency: str = "USD") -> str:
    if not currency or currency == "USD":
        return f"${value:,.2f}"
    return f"{currency} {value:,.2f}"


# --------------------------------------------------------------------------- #
# Anomaly correlation (related signals)
# --------------------------------------------------------------------------- #
def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson product-moment correlation coefficient (pure Python).

    Returns 0.0 when the series are too short to be meaningful or when either
    series has zero variance (a constant signal correlates with nothing).
    """
    n = len(xs)
    if n < 2 or len(ys) != n:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs)) * math.sqrt(
        sum((b - my) ** 2 for b in ys)
    )
    return (num / den) if den else 0.0


def _correlation_window_seconds(granularity: str) -> int:
    """Half-window (in seconds) around an anomaly timestamp per granularity."""
    periods = _CORRELATION_WINDOW_PERIODS.get(granularity, _CORRELATION_WINDOW_PERIODS["day"])
    return periods * _GRAN_SECONDS.get(granularity, _GRAN_SECONDS["day"])


def _align(
    own: list[MetricPoint], candidate: list[MetricPoint], tolerance: timedelta
) -> list[tuple[float, float]]:
    """Inner-join two sorted series by nearest timestamp within a tolerance.

    Both lists must be ordered ascending by timestamp. Each point is paired at
    most once; a pair is kept when the timestamps differ by no more than the
    tolerance (i.e. they fall in the same granularity bucket).
    """
    pairs: list[tuple[float, float]] = []
    i = j = 0
    while i < len(own) and j < len(candidate):
        delta = own[i].timestamp - candidate[j].timestamp
        if abs(delta) <= tolerance:
            pairs.append((own[i].value, candidate[j].value))
            i += 1
            j += 1
        elif delta < 0:
            i += 1
        else:
            j += 1
    return pairs


def find_related_datasets(anomaly, db_session: Session) -> list[dict]:
    """Find datasets in the same organization that moved with the anomaly.

    For every other dataset sharing the anomaly dataset's organization, the
    points around the anomaly timestamp are pulled (window size depends on each
    dataset's granularity), aligned to the anomaly dataset's own series by
    nearest timestamp, and scored with a Pearson correlation. Candidates with
    fewer than ``_CORRELATION_MIN_OVERLAP`` aligned points or ``|r| <= 0.6``
    are discarded.

    Returns up to five ``{dataset_id, dataset_name, correlation, direction}``
    entries, where ``direction`` is ``"same"`` (moved together) or
    ``"opposite"`` (moved inversely), sorted by ``abs(correlation)`` descending.
    """
    dataset_id = getattr(anomaly, "dataset_id", None)
    if dataset_id is None:
        return []
    ts = getattr(anomaly, "timestamp", None)
    if ts is None:
        return []
    ts = to_utc(ts)
    own = db_session.get(Dataset, dataset_id)
    if own is None or own.organization_id is None:
        return []

    own_win = _correlation_window_seconds(own.granularity)
    own_start = ts - timedelta(seconds=own_win)
    own_end = ts + timedelta(seconds=own_win)
    own_series = list(
        db_session.scalars(
            select(MetricPoint)
            .where(
                MetricPoint.dataset_id == own.id,
                MetricPoint.timestamp >= own_start,
                MetricPoint.timestamp <= own_end,
            )
            .order_by(MetricPoint.timestamp.asc())
        ).all()
    )

    candidates = list(
        db_session.scalars(
            select(Dataset).where(
                Dataset.organization_id == own.organization_id,
                Dataset.id != own.id,
            )
        ).all()
    )

    related: list[dict] = []
    for candidate in candidates:
        cand_win = _correlation_window_seconds(candidate.granularity)
        cand_start = ts - timedelta(seconds=cand_win)
        cand_end = ts + timedelta(seconds=cand_win)
        cand_series = list(
            db_session.scalars(
                select(MetricPoint)
                .where(
                    MetricPoint.dataset_id == candidate.id,
                    MetricPoint.timestamp >= cand_start,
                    MetricPoint.timestamp <= cand_end,
                )
                .order_by(MetricPoint.timestamp.asc())
            ).all()
        )
        tolerance = timedelta(
            seconds=max(_GRAN_SECONDS.get(own.granularity, 86400), _GRAN_SECONDS.get(candidate.granularity, 86400))
        )
        pairs = _align(own_series, cand_series, tolerance)
        if len(pairs) < _CORRELATION_MIN_OVERLAP:
            continue
        correlation = _pearson([a for a, _ in pairs], [b for _, b in pairs])
        if abs(correlation) <= _CORRELATION_THRESHOLD:
            continue
        related.append(
            {
                "dataset_id": candidate.id,
                "dataset_name": candidate.name,
                "correlation": round(correlation, 4),
                "direction": "same" if correlation >= 0 else "opposite",
            }
        )

    related.sort(key=lambda item: abs(item["correlation"]), reverse=True)
    return related[:_CORRELATION_MAX_RESULTS]
