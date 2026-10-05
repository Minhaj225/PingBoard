"""Application settings, loaded from the environment (12-factor style).

`Settings` is instantiated once and cached; import `get_settings()` rather than
constructing `Settings()` ad hoc so that a single parsed copy is shared.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime -----------------------------------------------------------
    ENV: Literal["dev", "test", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = ""

    # --- Datastores --------------------------------------------------------
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    # --- Auth --------------------------------------------------------------
    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Refresh-token cookie ----------------------------------------------
    REFRESH_COOKIE_NAME: str = "pb_refresh"
    # Scoped so the browser only ever sends it to the endpoints that consume it.
    REFRESH_COOKIE_PATH: str = "/auth"
    COOKIE_DOMAIN: str | None = None
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    # None => follow ENV (secure in prod). Set explicitly to override.
    COOKIE_SECURE: bool | None = None

    # --- Invites -----------------------------------------------------------
    INVITE_EXPIRE_HOURS: int = 72

    # --- Auth rate limiting ------------------------------------------------
    # Fixed window per client IP on /auth/login and /auth/register.
    AUTH_RATE_LIMIT: int = 10
    AUTH_RATE_LIMIT_WINDOW_S: int = 60

    # Public status pages: the only endpoint an anonymous caller can hit hard.
    PUBLIC_RATE_LIMIT: int = 60
    PUBLIC_RATE_LIMIT_WINDOW_S: int = 60

    # Authenticated writes.
    WRITE_RATE_LIMIT: int = 120
    WRITE_RATE_LIMIT_WINDOW_S: int = 60

    # --- Retention ---------------------------------------------------------
    RAW_RETENTION_DAYS: int = 30

    # --- OAuth (optional until Phase 1) ------------------------------------
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_REDIRECT_URI: str | None = None

    # --- Mail (optional until Phase 4) -------------------------------------
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@pingboard.local"
    SMTP_TLS: bool = True

    # --- Web ---------------------------------------------------------------
    # NoDecode: pydantic-settings would otherwise try to JSON-decode the raw
    # env value before the validator below sees it, so a plain
    # comma-separated string would fail to parse.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        """Accept either `a,b` or a JSON array in the env var."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [origin.strip() for origin in text.split(",") if origin.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def cookie_secure(self) -> bool:
        return self.is_prod if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def github_oauth_configured(self) -> bool:
        return bool(self.GITHUB_CLIENT_ID and self.GITHUB_CLIENT_SECRET)

    @property
    def database_url_str(self) -> str:
        return str(self.DATABASE_URL)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Required fields come from the environment, not from call arguments.
    return Settings()
