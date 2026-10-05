"""Shared Redis connection pool."""

from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

_pool: ConnectionPool = ConnectionPool.from_url(
    str(get_settings().REDIS_URL),
    decode_responses=True,
    max_connections=20,
)


def get_redis() -> Redis:
    """Return a client bound to the shared pool.

    Clients are cheap wrappers over the pool, so this is safe to call per
    request; the pool itself is closed once at shutdown.
    """
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    await _pool.aclose()
