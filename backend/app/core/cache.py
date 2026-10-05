"""Redis response caching.

Deliberately TTL-only with no invalidation. The cached reads here (public status
pages, uptime figures) are aggregates that change continuously anyway, so a
30-second window of staleness is invisible, while a write-through invalidation
scheme would add a failure mode for no real benefit.

A Redis outage must degrade to "slower", never to "broken": every operation
falls back to computing the value.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

T = TypeVar("T")

PUBLIC_STATUS_TTL_S = 30
UPTIME_TTL_S = 60


async def get_json(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
    except Exception:
        logger.warning("cache read failed; computing instead", exc_info=True)
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # A corrupt entry is not worth failing a request over.
        logger.warning("discarding malformed cache entry", extra={"cache_key": key})
        return None


async def set_json(key: str, value: Any, *, ttl_s: int) -> None:
    try:
        await get_redis().set(key, json.dumps(value, default=str), ex=ttl_s)
    except Exception:
        logger.warning("cache write failed", exc_info=True)


async def cached_json(
    key: str, ttl_s: int, compute: Callable[[], Awaitable[Any]]
) -> tuple[Any, bool]:
    """Return `(value, was_cached)`, computing and storing on a miss."""
    hit = await get_json(key)
    if hit is not None:
        return hit, True

    value = await compute()
    await set_json(key, value, ttl_s=ttl_s)
    return value, False


async def invalidate(*keys: str) -> None:
    """Drop specific keys. Used when a write makes staleness user-visible."""
    if not keys:
        return
    try:
        await get_redis().delete(*keys)
    except Exception:
        logger.warning("cache invalidation failed", exc_info=True)


def public_status_key(slug: str) -> str:
    return f"cache:public-status:{slug}"


def uptime_key(monitor_id: str, window: str) -> str:
    return f"cache:uptime:{monitor_id}:{window}"
