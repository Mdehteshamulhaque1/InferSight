"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    alert_rules,
    alerts,
    analytics,
    anomalies,
    audit,
    auth,
    datasets,
    forecasts,
    ingestion,
    insights,
    intelligence,
    organizations,
    reports,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(analytics.router)
api_router.include_router(anomalies.router)
api_router.include_router(forecasts.router)
api_router.include_router(insights.router)
api_router.include_router(reports.router)
api_router.include_router(intelligence.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
api_router.include_router(ingestion.router)
api_router.include_router(organizations.router)
api_router.include_router(alert_rules.router)
api_router.include_router(alert_rules.deliveries_router)
