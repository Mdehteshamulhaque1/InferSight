"""Intelligence engine: profiling, KPI discovery, root-cause analysis,
recommendations, business health scoring, and natural-language chat.

Like the analytics layer, all computation is deterministic pure Python over
MetricPoint lists — no external ML dependency, trivial to unit test, and
portable. The chat layer is rule-based by default; an LLM adapter can be
swapped in later without changing the response contract.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from app.services.analytics_service import find_related_datasets
from app.utils.time import to_utc

_GRAN_SECONDS = {"hour": 3600, "day": 86400, "week": 604800, "month": 2629800}


# --------------------------------------------------------------------------- #
# Small statistics helpers
# --------------------------------------------------------------------------- #
def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs)) * math.sqrt(
        sum((b - my) ** 2 for b in ys)
    )
    return (num / den) if den else 0.0


def _ols(values: list[float]) -> tuple[float, float]:
    """Least-squares (slope, r_squared) over the index axis."""
    n = len(values)
    if n < 2:
        return 0.0, 1.0
    xs = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    s_xx = sum((x - mean_x) ** 2 for x in xs)
    s_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    slope = s_xy / s_xx if s_xx else 0.0
    intercept = mean_y - slope * mean_x
    if s_xx == 0:
        r2 = 1.0
    else:
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, values))
        ss_tot = sum((y - mean_y) ** 2 for y in values)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot else 0.0
    return slope, max(0.0, min(1.0, r2))


def _pct(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / abs(previous) * 100.0


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #
def profile(points: list[Any], granularity: str = "day") -> dict[str, Any]:
    """Comprehensive statistical profile of a time series."""
    if not points:
        raise ValueError("no points to profile")
    values = [p.value for p in points]
    timestamps = [to_utc(p.timestamp) for p in points]
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)
    cv = std / abs(mean) if mean else 0.0
    median = statistics.median(values)
    start, end = timestamps[0], timestamps[-1]
    span_seconds = max((end - start).total_seconds(), 1.0)

    slope, r2 = _ols(values)
    direction = "flat"
    threshold = abs(mean) * 0.005 if mean else 1e-12
    if slope > threshold:
        direction = "up"
    elif slope < -threshold:
        direction = "down"
    slope_pct = (slope / abs(mean) * 100.0) if mean else 0.0

    lag = {"hour": 24, "day": 7, "week": 4, "month": 12}.get(granularity, 7)
    seasonal_corr = _pearson(values[:-lag], values[lag:]) if n > lag + 2 else 0.0
    if abs(seasonal_corr) >= 0.6:
        season_strength = "strong"
    elif abs(seasonal_corr) >= 0.3:
        season_strength = "moderate"
    else:
        season_strength = "weak"

    gran_seconds = _GRAN_SECONDS.get(granularity, 86400)
    deltas = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
    ]
    typical_delta = statistics.median(deltas) if deltas else gran_seconds
    expected = int(span_seconds / typical_delta) + 1 if typical_delta else n
    completeness = min(100.0, n / expected * 100.0) if expected else 100.0
    missing_periods = sum(1 for d in deltas if d > 1.5 * typical_delta)
    duplicates = sum(1 for _, c in Counter(timestamps).items() if c > 1)
    freshness_hours = (datetime.now(timezone.utc) - end).total_seconds() / 3600.0

    movers = []
    for i in range(1, n):
        if values[i - 1] != 0:
            change = _pct(values[i], values[i - 1])
            movers.append(
                {
                    "from": timestamps[i - 1],
                    "to": timestamps[i],
                    "from_value": round(values[i - 1], 6),
                    "to_value": round(values[i], 6),
                    "change_pct": round(change, 2),
                }
            )
    movers.sort(key=lambda m: abs(m["change_pct"]), reverse=True)

    ordered = sorted(
        zip(timestamps, values), key=lambda pair: pair[1], reverse=True
    )
    return {
        "count": n,
        "start": start,
        "end": end,
        "span_days": round(span_seconds / 86400.0, 2),
        "stats": {
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "mean": round(mean, 6),
            "median": round(median, 6),
            "std": round(std, 6),
            "sum": round(sum(values), 6),
            "cv": round(cv, 6),
        },
        "trend": {
            "slope_per_period_pct": round(slope_pct, 4),
            "direction": direction,
            "r_squared": round(r2, 4),
        },
        "seasonality": {
            "lag": lag,
            "correlation": round(seasonal_corr, 4),
            "strength": season_strength,
        },
        "quality": {
            "completeness_pct": round(completeness, 1),
            "expected_points": expected,
            "missing_periods": missing_periods,
            "duplicate_timestamps": duplicates,
            "negative_count": sum(1 for v in values if v < 0),
            "zero_count": sum(1 for v in values if v == 0),
            "freshness_hours": round(freshness_hours, 2),
        },
        "top_points": [
            {"timestamp": ts, "value": round(v, 6)} for ts, v in ordered[:5]
        ],
        "bottom_points": [
            {"timestamp": ts, "value": round(v, 6)} for ts, v in ordered[-5:][::-1]
        ],
        "biggest_movers": movers[:5],
    }


# --------------------------------------------------------------------------- #
# KPI discovery
# --------------------------------------------------------------------------- #
def discover_kpis(
    points: list[Any], granularity: str = "day", unit: str = "count"
) -> list[dict[str, Any]]:
    """Discover a ranked set of KPIs with recent vs prior-period deltas."""
    if not points:
        return []
    values = [p.value for p in points]
    timestamps = [to_utc(p.timestamp) for p in points]
    n = len(values)
    total = sum(values)
    mean = total / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    cv = std / abs(mean) if mean else 0.0

    midpoint = timestamps[n // 2]
    recent = [v for v, ts in zip(values, timestamps) if ts >= midpoint]
    prior = [v for v, ts in zip(values, timestamps) if ts < midpoint]
    period_change = _pct(sum(recent), sum(prior)) if recent and prior else 0.0

    growth_rates = [
        _pct(values[i], values[i - 1]) for i in range(1, n) if values[i - 1] != 0
    ]
    avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0.0

    peak_i = max(range(n), key=values.__getitem__)
    trough_i = min(range(n), key=values.__getitem__)
    latest_change = _pct(values[-1], values[-2]) if n >= 2 else 0.0

    def kpi(key: str, label: str, value: float, change: float | None, meta=None):
        item = {"key": key, "label": label, "value": round(value, 6), "unit": unit}
        if change is not None:
            item["change_pct"] = round(change, 2)
        if meta:
            item["metadata"] = meta
        return item

    return [
        kpi("total", "Total", total, period_change, {"periods": n}),
        kpi("average", "Average", mean, None, {"periods": n}),
        kpi(
            "latest",
            "Latest",
            values[-1],
            latest_change,
            {"timestamp": timestamps[-1]},
        ),
        kpi(
            "peak",
            "Peak",
            values[peak_i],
            None,
            {"timestamp": timestamps[peak_i]},
        ),
        kpi(
            "trough",
            "Trough",
            values[trough_i],
            None,
            {"timestamp": timestamps[trough_i]},
        ),
        kpi("growth", "Growth (per-period avg)", avg_growth, None, {"samples": len(growth_rates)}),
        kpi("volatility", "Volatility (CV)", cv, None, {"interpretation": "lower is more stable"}),
        kpi("span_days", "Coverage", round((timestamps[-1] - timestamps[0]).total_seconds() / 86400.0, 2), None),
    ]


# --------------------------------------------------------------------------- #
# Root-cause analysis
# --------------------------------------------------------------------------- #
def root_cause(
    points: list[Any],
    anomaly: Any,
    granularity: str = "day",
    db_session=None,
) -> dict[str, Any]:
    """Explain what likely drove a specific anomaly.

    When a ``db_session`` is supplied, the anomaly is also cross-checked
    against other datasets in the same organization and the result is exposed
    under ``related_signals`` (see ``analytics_service.find_related_datasets``).
    """
    timestamps = [to_utc(p.timestamp) for p in points]
    values = [p.value for p in points]
    try:
        idx = next(i for i, ts in enumerate(timestamps) if ts >= to_utc(anomaly.timestamp))
    except StopIteration:
        idx = len(points) - 1

    actual = anomaly.value if anomaly.value is not None else values[idx]
    expected = anomaly.expected if anomaly.expected is not None else _median(values)
    delta = actual - expected
    delta_pct = _pct(actual, expected)

    gran_seconds = _GRAN_SECONDS.get(granularity, 86400)
    window_seconds = gran_seconds * 2
    window_start = to_utc(anomaly.timestamp) - __import__("datetime").timedelta(seconds=window_seconds)
    window_end = to_utc(anomaly.timestamp) + __import__("datetime").timedelta(seconds=window_seconds)

    segments: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    segment_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    baseline: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    baseline_start = to_utc(anomaly.timestamp) - __import__("datetime").timedelta(seconds=window_seconds * 2)

    for ts, value, meta in zip(timestamps, values, [p.meta for p in points]):
        meta = meta or {}
        if not isinstance(meta, dict):
            continue
        for dim, seg in meta.items():
            key = str(seg)
            if window_start <= ts <= window_end:
                segments[dim][key].append(value)
                segment_counts[dim][key] += 1
            elif baseline_start <= ts < window_start:
                baseline[dim][key].append(value)

    contributing: list[dict[str, Any]] = []
    for dim, groups in segments.items():
        total_window = sum(sum(v) for v in groups.values())
        for seg, vals in groups.items():
            window_mean = sum(vals) / len(vals)
            base_vals = baseline.get(dim, {}).get(seg, [])
            base_mean = sum(base_vals) / len(base_vals) if base_vals else window_mean
            if base_mean == 0:
                continue
            weight = sum(vals) / total_window if total_window else 0.0
            if abs(_pct(window_mean, base_mean)) < 5:
                continue
            contributing.append(
                {
                    "dimension": dim,
                    "segment": seg,
                    "value": round(window_mean, 4),
                    "baseline": round(base_mean, 4),
                    "change_pct": round(_pct(window_mean, base_mean), 2),
                    "weight": round(weight, 4),
                }
            )
    contributing.sort(key=lambda c: abs(c["change_pct"]) * c["weight"], reverse=True)

    overall_mean = sum(values) / len(values)
    dow_groups: dict[int, list[float]] = defaultdict(list)
    for ts, v in zip(timestamps, values):
        dow_groups[ts.weekday()].append(v)
    month_groups: dict[int, list[float]] = defaultdict(list)
    for ts, v in zip(timestamps, values):
        month_groups[ts.month].append(v)

    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    time_effects: list[dict[str, Any]] = []
    anomaly_dow = to_utc(anomaly.timestamp).weekday()
    dow_avg = sum(dow_groups[anomaly_dow]) / len(dow_groups[anomaly_dow]) if dow_groups[anomaly_dow] else overall_mean
    time_effects.append(
        {
            "factor": "day_of_week",
            "value": dow_names[anomaly_dow],
            "relative_change_pct": round(_pct(dow_avg, overall_mean), 2),
            "points": len(dow_groups[anomaly_dow]),
        }
    )
    anomaly_month = to_utc(anomaly.timestamp).month
    month_avg = sum(month_groups[anomaly_month]) / len(month_groups[anomaly_month]) if month_groups[anomaly_month] else overall_mean
    time_effects.append(
        {
            "factor": "month",
            "value": f"{anomaly_month:02d}",
            "relative_change_pct": round(_pct(month_avg, overall_mean), 2),
            "points": len(month_groups[anomaly_month]),
        }
    )

    hypotheses: list[dict[str, str]] = []
    direction_word = "above" if actual > expected else "below"
    hypotheses.append(
        {
            "title": f"Level shift {direction_word} expectation",
            "evidence": (
                f"observed {actual:,.2f} vs expected {expected:,.2f} "
                f"({delta_pct:+.1f}%)"
            ),
            "confidence": "high" if abs(delta_pct) >= 20 else "medium",
        }
    )
    if contributing:
        top = contributing[0]
        hypotheses.append(
            {
                "title": f"{top['dimension']} segment '{top['segment']}' drove the move",
                "evidence": (
                    f"segment moved {top['change_pct']:+.1f}% vs its baseline "
                    f"and accounts for {top['weight'] * 100:.0f}% of volume"
                ),
                "confidence": "high" if abs(top["change_pct"]) >= 30 else "medium",
            }
        )
    dow_effect = time_effects[0]["relative_change_pct"]
    if abs(dow_effect) >= 10:
        hypotheses.append(
            {
                "title": f"Day-of-week pattern ({dow_names[anomaly_dow]})",
                "evidence": (
                    f"{dow_names[anomaly_dow]}s run {dow_effect:+.1f}% vs the "
                    f"series average"
                ),
                "confidence": "medium",
            }
        )
    if len(hypotheses) < 2:
        hypotheses.append(
            {
                "title": "No dominant segment or calendar pattern found",
                "evidence": "move appears broad-based across dimensions and days",
                "confidence": "low",
            }
        )

    return {
        "timestamp": to_utc(anomaly.timestamp),
        "actual": round(actual, 6),
        "expected": round(expected, 6),
        "delta": round(delta, 6),
        "delta_pct": round(delta_pct, 2),
        "direction": "spike" if actual > expected else "drop",
        "contributing_segments": contributing[:5],
        "time_effects": time_effects,
        "hypotheses": hypotheses[:3],
        "related_signals": (
            find_related_datasets(anomaly, db_session) if db_session else []
        ),
    }


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #
def recommend(
    points: list[Any],
    profile_data: dict[str, Any] | None = None,
    anomalies: list[Any] | None = None,
    granularity: str = "day",
) -> list[dict[str, str]]:
    """Deterministic, rule-based actions ranked by urgency."""
    prof = profile_data or profile(points, granularity)
    anomalies = anomalies or []
    values = [p.value for p in points]
    recs: list[dict[str, str]] = []

    critical = [a for a in anomalies if getattr(a, "severity", "") == "critical"]
    recent = [
        a
        for a in anomalies
        if (to_utc(points[-1].timestamp) - to_utc(a.timestamp)).total_seconds()
        <= _GRAN_SECONDS.get(granularity, 86400) * 4
    ]
    if critical:
        recs.append(
            {
                "id": "rec-critical-anomaly",
                "severity": "critical",
                "category": "monitoring",
                "action": "Investigate the critical anomaly now",
                "rationale": (
                    f"{len(critical)} critical deviation(s) exceed twice the "
                    f"detection threshold"
                ),
                "impact": "Stop a material loss before it compounds",
            }
        )
    if recent and not critical:
        recs.append(
            {
                "id": "rec-recent-anomaly",
                "severity": "warning",
                "category": "monitoring",
                "action": "Review recent unusual movement",
                "rationale": (
                    f"{len(recent)} deviation(s) detected in the last "
                    f"4 periods"
                ),
                "impact": "Confirm the cause before it becomes a trend",
            }
        )

    trend = prof["trend"]
    if trend["direction"] == "down" and abs(trend["slope_per_period_pct"]) >= 1.0:
        recs.append(
            {
                "id": "rec-declining-trend",
                "severity": "warning",
                "category": "growth",
                "action": "Diagnose the persistent decline",
                "rationale": (
                    f"series is falling {abs(trend['slope_per_period_pct']):.1f}% "
                    f"per period (R²={trend['r_squared']:.2f})"
                ),
                "impact": "Arresting the decline recovers compounding losses",
            }
        )

    cv = prof["stats"]["cv"]
    if cv >= 0.5:
        recs.append(
            {
                "id": "rec-volatility",
                "severity": "warning",
                "category": "stability",
                "action": "Stabilize high variability",
                "rationale": f"coefficient of variation is {cv:.2f}",
                "impact": "Predictability lowers inventory and cash-buffer costs",
            }
        )

    quality = prof["quality"]
    if quality["completeness_pct"] < 80:
        recs.append(
            {
                "id": "rec-completeness",
                "severity": "warning",
                "category": "data_quality",
                "action": "Backfill missing periods",
                "rationale": (
                    f"only {quality['completeness_pct']:.0f}% of expected periods "
                    f"are present ({quality['missing_periods']} gaps)"
                ),
                "impact": "Complete data materially improves forecast accuracy",
            }
        )
    if quality["freshness_hours"] > _GRAN_SECONDS.get(granularity, 86400) / 3600 * 2:
        recs.append(
            {
                "id": "rec-freshness",
                "severity": "warning",
                "category": "data_quality",
                "action": "Verify the data pipeline",
                "rationale": (
                    f"last point is {quality['freshness_hours']:.0f}h old, more "
                    f"than 2x the reporting cadence"
                ),
                "impact": "Keep alerts and decisions based on current data",
            }
        )

    if prof["seasonality"]["strength"] in ("strong", "moderate"):
        recs.append(
            {
                "id": "rec-seasonality",
                "severity": "info",
                "category": "planning",
                "action": "Build for the detected cycle",
                "rationale": (
                    f"{prof['seasonality']['strength']} autocorrelation at "
                    f"lag {prof['seasonality']['lag']}"
                ),
                "impact": "Shape capacity and promotion around the cycle",
            }
        )

    if len(values) >= 3 and all(
        values[i] < values[i - 1] for i in range(len(values) - 3, len(values))
    ):
        recs.append(
            {
                "id": "rec-recent-decline",
                "severity": "info",
                "category": "growth",
                "action": "Trace the last three down periods",
                "rationale": "the last three points are successively lower",
                "impact": "Catch funnel or delivery friction early",
            }
        )

    if not recs:
        recs.append(
            {
                "id": "rec-sustain",
                "severity": "info",
                "category": "growth",
                "action": "Maintain current momentum",
                "rationale": (
                    f"series is {trend['direction']} with low variability "
                    f"and good completeness"
                ),
                "impact": "Protect and extend the healthy baseline",
            }
        )
    return recs[:6]


# --------------------------------------------------------------------------- #
# Business health score
# --------------------------------------------------------------------------- #
def health_score(
    points: list[Any],
    profile_data: dict[str, Any] | None = None,
    anomalies: list[Any] | None = None,
    granularity: str = "day",
) -> dict[str, Any]:
    """Composite 0-100 health score with weighted, transparent components."""
    prof = profile_data or profile(points, granularity)
    anomalies = anomalies or []
    quality = prof["quality"]
    trend = prof["trend"]
    stats = prof["stats"]
    gran_seconds = _GRAN_SECONDS.get(granularity, 86400) / 3600.0  # hours

    freshness = max(
        0.0, 100.0 - (quality["freshness_hours"] / gran_seconds - 1.0) * 50.0
    )
    completeness = quality["completeness_pct"]
    stability = max(0.0, 100.0 - stats["cv"] * 100.0)
    anomaly_rate = max(0.0, 100.0 - len(anomalies) * 15.0)
    if trend["direction"] == "up":
        momentum = min(100.0, 60.0 + abs(trend["slope_per_period_pct"]) * 5.0)
    elif trend["direction"] == "down":
        momentum = max(10.0, 60.0 - abs(trend["slope_per_period_pct"]) * 8.0)
    else:
        momentum = 60.0

    components = [
        ("freshness", "Data freshness", freshness, 0.30,
         f"last point {quality['freshness_hours']:.0f}h ago (cadence {gran_seconds:.0f}h)"),
        ("completeness", "Completeness", completeness, 0.25,
         f"{quality['completeness_pct']:.0f}% of expected periods, {quality['missing_periods']} gaps"),
        ("stability", "Stability", stability, 0.20,
         f"volatility (CV) {stats['cv']:.2f}"),
        ("anomaly_rate", "Anomaly pressure", anomaly_rate, 0.15,
         f"{len(anomalies)} anomaly/ies in the window"),
        ("momentum", "Momentum", momentum, 0.10,
         f"{trend['direction']} {abs(trend['slope_per_period_pct']):.1f}%/period"),
    ]
    score = sum(c[2] * c[3] for c in components)
    score = max(0, min(100, round(score)))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 45 else "F"
    verdict = (
        "Healthy and predictable"
        if score >= 75
        else "Watch carefully — fixable gaps"
        if score >= 55
        else "At risk — needs intervention"
    )
    weakest = min(components, key=lambda c: c[2])
    return {
        "score": score,
        "grade": grade,
        "verdict": verdict,
        "components": [
            {
                "key": c[0],
                "label": c[1],
                "score": round(c[2], 1),
                "weight": c[3],
                "detail": c[4],
            }
            for c in components
        ],
    }


# --------------------------------------------------------------------------- #
# Natural-language chat (rule-based intents)
# --------------------------------------------------------------------------- #
_INTENT_RULES: list[tuple[str, re.Pattern]] = [
    ("greeting", re.compile(r"\b(hi|hello|hey|help|what can you do)\b", re.I)),
    ("anomaly", re.compile(r"\banomal|spike|drop|outlier|weird|abnormal|unusual\b", re.I)),
    ("trend", re.compile(r"\btrend|growth|declin|direction|upward|downward|improv|worsen\b", re.I)),
    ("forecast", re.compile(r"\bforecast|predict|project|next (month|week|quarter)|outlook|future\b", re.I)),
    ("health", re.compile(r"\bhealth|score|doing|wellbeing|rating\b", re.I)),
    ("recommend", re.compile(r"\brecommend|suggest|should|advise|action|what to do\b", re.I)),
    ("extremes", re.compile(r"\btop|best|worst|peak|trough|highest|lowest|record\b", re.I)),
    ("compare", re.compile(r"\bcompare|vs|versus|better|worse than\b", re.I)),
]


def _resolve_intent(message: str) -> str:
    for intent, pattern in _INTENT_RULES:
        if pattern.search(message):
            return intent
    return "summary"


def chat(
    message: str,
    points: list[Any],
    dataset: Any,
    anomalies: list[Any] | None = None,
    granularity: str = "day",
) -> dict[str, Any]:
    """Answer a free-text question with a rule-based reply + structured data."""
    intent = _resolve_intent(message)
    prof = profile(points, granularity)
    kpis = discover_kpis(points, granularity, dataset.unit)
    anomalies = anomalies or []
    stats = prof["stats"]
    trend = prof["trend"]

    name = dataset.name
    direction_word = trend["direction"]
    trend_line = (
        f"{name} is trending {direction_word} at "
        f"{abs(trend['slope_per_period_pct']):.1f}% per period "
        f"(fit R²={trend['r_squared']:.2f})."
    )

    followups = [
        "What are the anomalies?",
        "How healthy is this metric?",
        "What should I do next?",
        "Forecast the next few periods.",
    ]

    if intent == "greeting":
        reply = (
            f"Hi. I can analyze {name} in plain language — ask about trends, "
            f"anomalies, health, forecasts, or what to do next."
        )
    elif intent == "anomaly":
        if anomalies:
            worst = max(anomalies, key=lambda a: abs(a.score))
            reply = (
                f"I found {len(anomalies)} deviation(s) in {name}. The most "
                f"significant was on {worst.timestamp.date()} "
                f"({worst.direction}, score {worst.score:.1f}σ) — "
                f"{worst.reason}."
            )
            followups = [
                "Why did that anomaly happen?",
                "What should I do next?",
                "How healthy is this metric?",
            ]
        else:
            reply = f"No anomalies detected in {name}. The series is behaving as expected."
    elif intent == "trend":
        reply = (
            f"{trend_line} The series averages {stats['mean']:,.2f} per period, "
            f"ranging from {stats['min']:,.2f} to {stats['max']:,.2f}."
        )
    elif intent == "forecast":
        latest = stats["max"]
        reply = (
            f"Based on the current slope of {abs(trend['slope_per_period_pct']):.1f}%/period "
            f"({trend['direction']}), {name} is projected to continue "
            f"{'rising toward' if trend['direction'] == 'up' else 'declining toward'} "
            f"{latest:,.2f} unless conditions change. Seasonality is "
            f"{prof['seasonality']['strength']} (lag {prof['seasonality']['lag']})."
        )
    elif intent == "health":
        hs = health_score(points, prof, anomalies, granularity)
        reply = (
            f"{name} scores {hs['score']}/100 ({hs['grade']}) — "
            f"{hs['verdict']}. Strongest area: "
            f"{max(hs['components'], key=lambda c: c['score'])['label']}; "
            f"watch: {min(hs['components'], key=lambda c: c['score'])['label']}."
        )
    elif intent == "recommend":
        recs = recommend(points, prof, anomalies, granularity)
        top = recs[0]
        reply = (
            f"My top recommendation: {top['action']}. {top['rationale']}. "
            f"{len(recs)} action(s) total."
        )
    elif intent == "extremes":
        peak = kpis[3]
        trough = kpis[4]
        reply = (
            f"Peak for {name} was {peak['value']:,.2f} at "
            f"{peak['metadata']['timestamp'].date()}; trough was "
            f"{trough['value']:,.2f} at {trough['metadata']['timestamp'].date()}."
        )
    elif intent == "compare":
        latest = kpis[2]
        change = latest.get("change_pct")
        reply = (
            f"The latest period for {name} was {latest['value']:,.2f}"
            + (
                f", {change:+.1f}% vs the previous period." if change is not None else "."
            )
        )
    else:  # summary
        reply = (
            f"{trend_line} {len(points)} points span "
            f"{prof['span_days']:.0f} days; average {stats['mean']:,.2f}, "
            f"peaking at {stats['max']:,.2f}. Data completeness is "
            f"{prof['quality']['completeness_pct']:.0f}% and volatility "
            f"(CV) is {stats['cv']:.2f}."
        )

    return {
        "intent": intent,
        "reply": reply,
        "data": {
            "profile": prof,
            "kpis": kpis,
            "anomalies": len(anomalies),
            "health": health_score(points, prof, anomalies, granularity),
        },
        "followups": followups,
    }
