"""Redis-backed fixed-window rate limiting.

Phase 1 uses this only to slow credential brute-forcing on the auth endpoints;
Phase 6 generalises it to the rest of the API.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    """Best-effort client address.

    `X-Forwarded-For` is only meaningful when the app sits behind a proxy that
    sets it; treat it as a hint for rate-limit bucketing, never for authz.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_fixed_window(*, key: str, limit: int, window_s: int) -> None:
    """Raise 429 once `limit` hits land in the current `window_s` bucket.

    A Redis outage must not lock users out of logging in, so a failure here is
    logged and treated as "allowed" rather than propagated.
    """
    redis = get_redis()
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_s)
            count, _ = await pipe.execute()
    except Exception:
        logger.warning("rate limiter unavailable; allowing request", exc_info=True)
        return

    if int(count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(window_s)},
        )


async def auth_rate_limit(request: Request) -> None:
    """Dependency guarding the credential endpoints.

    Deliberately separate from (and tighter than) the general API limit: these
    are the endpoints worth brute-forcing.
    """
    settings = get_settings()
    bucket = f"rl:auth:{request.url.path}:{client_ip(request)}"
    await enforce_fixed_window(
        key=bucket,
        limit=settings.AUTH_RATE_LIMIT,
        window_s=settings.AUTH_RATE_LIMIT_WINDOW_S,
    )


async def public_rate_limit(request: Request) -> None:
    """Dependency guarding the unauthenticated status-page endpoint.

    This is the only route an anonymous caller can hit in volume, so it gets
    its own budget rather than sharing one with authenticated traffic.
    """
    settings = get_settings()
    bucket = f"rl:public:{client_ip(request)}"
    await enforce_fixed_window(
        key=bucket,
        limit=settings.PUBLIC_RATE_LIMIT,
        window_s=settings.PUBLIC_RATE_LIMIT_WINDOW_S,
    )


async def write_rate_limit(request: Request) -> None:
    """Dependency guarding authenticated write endpoints.

    Bucketed by IP rather than by user: an attacker with a valid token can
    create accounts, and per-user limits would not slow them down.
    """
    settings = get_settings()
    bucket = f"rl:write:{client_ip(request)}"
    await enforce_fixed_window(
        key=bucket,
        limit=settings.WRITE_RATE_LIMIT,
        window_s=settings.WRITE_RATE_LIMIT_WINDOW_S,
    )
