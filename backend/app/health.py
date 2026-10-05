"""Liveness and readiness endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Process is up. Deliberately touches no dependency."""
    return HealthResponse()


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReadinessResponse:
    """Dependencies are reachable. Returns 503 when any of them is not."""
    db_ok = await _check_db(db)
    redis_ok = await _check_redis()

    ready = db_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if ready else "degraded", database=db_ok, redis=redis_ok)


async def _check_db(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("readiness: database unreachable", exc_info=True)
        return False
    return True


async def _check_redis() -> bool:
    client = get_redis()
    try:
        await client.ping()
    except Exception:
        logger.warning("readiness: redis unreachable", exc_info=True)
        return False
    return True
