"""Async SQLAlchemy 2.0 engine, session factory and the `get_db` dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model.

    Models are registered by importing them in `app.core.models_registry`, which
    Alembic's `env.py` imports so autogenerate sees the full metadata.
    """


def create_engine(url: str | None = None, **kwargs: Any) -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        url or settings.database_url_str,
        echo=False,
        pool_pre_ping=True,
        **kwargs,
    )


engine: AsyncEngine = create_engine()

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session that is rolled back on error.

    Routes commit explicitly; anything uncommitted when the request ends is
    discarded, so a handler that raises never leaves a partial write behind.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()
