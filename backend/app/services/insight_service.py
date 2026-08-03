"""Insight generation engine.

Produces human-readable, data-driven narratives from a dataset's analytics.
The default pipeline is fully rule-based and deterministic. When an OpenAI
API key is configured, the rule-based draft is optionally enriched into a more
executive-friendly summary; the LLM path degrades silently on any failure so
insight generation never breaks the API.
"""

from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Dataset, Insight, User
from app.schemas.analytics import Kpi, Trend
from app.services.analytics_service import fmt_amount
from app.services.anomaly_service import detect
from app.services.forecast_service import forecast

logger = logging.getLogger("infersight.insights")

_LLM_TIMEOUT = 12.0


def _severity_for(trend: Trend, anomaly_summary: dict) -> str:
    if anomaly_summary.get("critical", 0) > 0:
        return "critical"
    if anomaly_summary.get("warning", 0) > 0 or trend.direction != "up":
        return "warning"
    return "info"


def generate_dataset_insight(
    db: Session,
    user: User,
    dataset: Dataset,
    points: list[object],
    kpis: list[Kpi],
    trend: Trend,
) -> Insight:
    """Build a rule-based insight, optionally LLM-enriched, and persist it."""
    kpi_map = {k.key: k for k in kpis}
    latest = kpi_map.get("latest")
    growth = kpi_map.get("growth")
    total = kpi_map.get("total")

    anom_response = detect(points)
    anom_count = anom_response.summary.get("total", 0)

    forecast_response = None
    try:
        forecast_response = forecast(points, horizon=14, method="auto", granularity=dataset.granularity)
    except Exception:
        logger.warning("forecast skipped during insight generation for dataset %s", dataset.id)

    change_txt = f"{abs(latest.change_pct):.1f}%" if latest and latest.change_pct is not None else "stable"
    direction_txt = {
        "up": "an upward",
        "down": "a downward",
        "flat": "a flat",
    }.get(trend.direction, "a mixed")
    amount_txt = fmt_amount(total.value, dataset.currency) if total else "n/a"

    title = (
        f"{dataset.name} trending {trend.direction} with {change_txt} latest change"
    )
    body_parts = [
        f"{dataset.name} ({dataset.metric_type}, granularity {dataset.granularity}) "
        f"shows {direction_txt} trend over the recorded period (slope {trend.slope:+.4f}, "
        f"R² {trend.r_squared:.3f}).",
        f"Total value across the series is {amount_txt} with an average of "
        f"{fmt_amount(kpi_map.get('average').value, dataset.currency) if kpi_map.get('average') else 'n/a'} "
        f"per period.",
        f"The latest period is {change_txt} versus the previous period.",
        f"{anom_count} anomalous {'point' if anom_count == 1 else 'points'} were detected "
        f"({anom_response.summary.get('spikes', 0)} spikes, {anom_response.summary.get('drops', 0)} drops).",
    ]
    if growth and growth.value:
        body_parts.append(
            f"Average period-over-period growth is {growth.value:+.2f}%."
        )
    if forecast_response and forecast_response.points:
        horizon_total = sum(p.value for p in forecast_response.points)
        body_parts.append(
            f"Using {forecast_response.method} smoothing, the next "
            f"{forecast_response.horizon} periods are projected at approximately "
            f"{fmt_amount(horizon_total, dataset.currency)} aggregate."
        )

    if latest and latest.change_pct is not None and latest.change_pct < 0:
        body_parts.append(
            "Recommendation: investigate recent drivers of decline before the next cycle."
        )
    elif anom_count:
        body_parts.append(
            "Recommendation: review the flagged anomalies for operational impact."
        )

    severity = _severity_for(trend, anom_response.summary)

    raw_body = " ".join(body_parts)

    # Optional LLM enrichment.
    llm_body = None
    settings = get_settings()
    if settings.openai_api_key:
        try:
            llm_body = _llm_summary(dataset.name, kpis, trend, anom_response.summary, raw_body)
        except Exception:
            logger.exception("LLM insight enrichment failed; falling back to rule-based")

    insight = Insight(
        dataset_id=dataset.id,
        user_id=user.id,
        kind="insight",
        severity=severity,
        title=title,
        body=llm_body or raw_body,
        payload={
            "trend": trend.model_dump(mode="json"),
            "anomaly_summary": anom_response.summary,
            "rule_based": raw_body,
            "llm": bool(llm_body),
        },
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight


def _llm_summary(name: str, kpis: list[Kpi], trend: Trend, anom_summary: dict, draft: str) -> str:
    settings = get_settings()
    kpi_lines = "\n".join(
        f"- {k.label}: {k.value}{' (' + str(k.change_pct) + '% vs prev)' if k.change_pct is not None else ''}"
        for k in kpis
    )
    prompt = (
        f"Dataset: {name}\nTrend: {trend.direction} (slope {trend.slope:.4f}, R² {trend.r_squared:.3f})\n"
        f"Anomalies: {anom_summary}\nKPIs:\n{kpi_lines}\n"
        f"Rule-based draft: {draft}\n\n"
        "Rewrite as a concise executive summary (max 120 words) for a business "
        "analyst dashboard. Use plain language, numbers, and one recommendation. "
        "Reply with JSON: {\"summary\": \"...\"}"
    )
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        },
        timeout=_LLM_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return parsed["summary"]


def list_insights(
    db: Session,
    user: User,
    dataset_id: int | None,
    kind: str | None,
    page: int,
    limit: int,
) -> tuple[list[Insight], int]:
    stmt = select(Insight).join(Dataset, Insight.dataset_id == Dataset.id).where(
        Dataset.owner_id == user.id
    )
    count_stmt = (
        select(func.count(Insight.id)).join(Dataset, Insight.dataset_id == Dataset.id).where(
            Dataset.owner_id == user.id
        )
    )
    if dataset_id is not None:
        stmt = stmt.where(Insight.dataset_id == dataset_id)
        count_stmt = count_stmt.where(Insight.dataset_id == dataset_id)
    if kind is not None:
        stmt = stmt.where(Insight.kind == kind)
        count_stmt = count_stmt.where(Insight.kind == kind)

    total = db.scalar(count_stmt) or 0
    items = db.scalars(
        stmt.order_by(Insight.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return list(items), total


def delete_insight(db: Session, insight_id: int, user: User) -> None:
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise ValueError("insight not found")
    dataset = db.get(Dataset, insight.dataset_id) if insight.dataset_id else None
    if dataset is not None and dataset.owner_id != user.id:
        raise PermissionError("you do not have access to this insight")
    db.delete(insight)
    db.commit()
