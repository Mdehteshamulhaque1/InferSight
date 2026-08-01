"""FastAPI application entry point for InferSight."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.database.session import init_db

APP_TITLE = "InferSight API"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "AI-powered intelligent analytics platform"

TAGS_METADATA = [
    {"name": "System", "description": "Operational endpoints for service status."},
    {"name": "Authentication", "description": "Register, login, tokens, sessions."},
    {"name": "Datasets", "description": "Dataset and metric-point management."},
    {"name": "Analytics", "description": "KPIs, resampled series, and trend analysis."},
    {"name": "Anomalies", "description": "Rolling z-score anomaly detection."},
    {"name": "Forecasting", "description": "Time-series forecasting with confidence bands."},
    {"name": "Insights", "description": "AI-generated narrative insights."},
    {"name": "Reports", "description": "CSV, Excel, and PDF report exports."},
]

logger = logging.getLogger("infersight")


def _configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    _configure_logging(settings)

    logger.info("Starting %s v%s (%s)", settings.app_name, settings.app_version, settings.environment)
    if settings.auto_create_tables:
        try:
            init_db()
            logger.info("Database schema initialized; bootstrap admin ensured")
        except Exception:
            logger.exception("Database initialization failed")
            raise
    yield
    logger.info("InferSight API shutdown complete")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        lifespan=lifespan,
        openapi_tags=TAGS_METADATA,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "an unexpected error occurred", "error": type(exc).__name__},
        )

    @app.get("/", tags=["System"], summary="Platform welcome message")
    async def root() -> dict[str, str]:
        return {"message": "Welcome to InferSight API", "docs": "/docs"}

    @app.get("/health", tags=["System"], summary="Service health check")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "version": APP_VERSION}

    return app


# Expose the ASGI app for Uvicorn and other ASGI servers.
app = create_app()
