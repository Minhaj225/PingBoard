"""FastAPI application factory and ASGI entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.channels.router import router as channels_router
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.logging import configure_logging
from app.core.redis import close_redis
from app.health import router as health_router
from app.incidents.router import router as incidents_router
from app.monitors.router import router as monitors_router
from app.orgs.api_key_router import router as api_keys_router
from app.orgs.router import router as orgs_router
from app.status_pages.router import public_router, uptime_router
from app.status_pages.router import router as status_pages_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Release pooled connections so reloads and container stops are clean.
    await dispose_engine()
    await close_redis()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL, json_output=settings.ENV != "dev")

    app = FastAPI(
        title="PingBoard API",
        version="0.1.0",
        summary="Multi-tenant uptime monitoring with public status pages.",
        lifespan=lifespan,
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,  # refresh token travels as an httpOnly cookie
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(orgs_router)
    app.include_router(api_keys_router)
    app.include_router(monitors_router)
    app.include_router(incidents_router)
    app.include_router(channels_router)
    app.include_router(status_pages_router)
    app.include_router(uptime_router)
    app.include_router(public_router)
    return app


app = create_app()
