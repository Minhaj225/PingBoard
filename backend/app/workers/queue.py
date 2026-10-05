"""Enqueueing jobs from the API process.

The API has no ARQ worker context, so it opens a short-lived pool when it needs
to queue work. Delivery itself always happens in the worker.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def enqueue_notification(org_id: str, payload: dict[str, Any]) -> bool:
    """Queue a notification fan-out. Returns whether it was accepted.

    Never raises: a request that succeeded must not be reported as failed
    because the queue was briefly unreachable.
    """
    try:
        pool = await create_pool(RedisSettings.from_dsn(str(get_settings().REDIS_URL)))
    except Exception:
        logger.exception("could not connect to the job queue")
        return False

    try:
        await pool.enqueue_job("deliver_notification", org_id, payload)
        return True
    except Exception:
        logger.exception("could not enqueue notification")
        return False
    finally:
        await pool.aclose()
