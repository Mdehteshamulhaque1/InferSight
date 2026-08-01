"""Application settings for InferSight.

Settings are loaded from environment variables first and fall back to the
backend/.env file. The loader is cached so that a single validated instance is
shared across the process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve the backend root so the settings loader reads backend/.env consistently.
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables and .env."""

    # Application metadata and runtime mode.
    app_name: str = Field(default="InferSight API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # API routing configuration.
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    # CORS origins (comma separated list).
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    # Security primitives required for token signing and validation.
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )

    # Primary datastore and cache connections.
    database_url: str = Field(..., alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    auto_create_tables: bool = Field(default=True, alias="AUTO_CREATE_TABLES")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")

    # Deployed frontend origin, e.g. Render's <service>.onrender.com hostname.
    # When set, it is appended to the allowed CORS origins automatically.
    frontend_url: str = Field(default="", alias="FRONTEND_URL")

    # Alert routing and async delivery (Celery broker falls back to REDIS_URL).
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    celery_broker_url: str = Field(default="", alias="CELERY_BROKER_URL")
    celery_enabled: bool = Field(default=True, alias="CELERY_ENABLED")

    # Logging controls for structured observability.
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM provider credentials used by downstream integrations.
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # Bootstrap administrator created on first startup.
    admin_email: str = Field(default="admin@infersight.dev", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="admin12345", alias="ADMIN_PASSWORD")
    admin_name: str = Field(default="InferSight Admin", alias="ADMIN_NAME")

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_postgres_scheme(cls, value: str) -> str:
        # Generic postgres:// or postgresql:// URLs (e.g. Render's injected
        # connection string uses postgres://) default to the psycopg2 driver
        # in SQLAlchemy; route them to psycopg v3, which ships binary wheels
        # for current Python releases.
        if value.startswith(("postgres://", "postgresql://")):
            scheme = value.split("://", 1)[0] + "://"
            return "postgresql+psycopg://" + value[len(scheme) :]
        return value

    @field_validator("frontend_url")
    @classmethod
    def normalize_frontend_origin(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            return f"https://{value}"
        return value

    @field_validator("cors_origins")
    @classmethod
    def parse_origins(cls, value: str) -> list[str]:
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins
        if isinstance(raw, list):
            origins = raw
        else:
            origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance for application-wide reuse."""
    return Settings()
