"""ARQ worker entrypoint.

Run with:  arq app.workers.main.WorkerSettings

The worker shares the API's image and code but none of its process: the API
never makes outbound checks, and the worker never serves HTTP.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import httpx
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.logging import configure_logging
from app.workers.maintenance import prune_old_checks, rollup_previous_hour
from app.workers.notify import deliver_notification
from app.workers.runner import run_monitor_check, scheduler_tick

logger = logging.getLogger(__name__)

# The scheduler ticks far more often than the shortest monitor interval (30s)
# so a monitor is never meaningfully late for its slot.
SCHEDULER_TICK_SECONDS = {0, 10, 20, 30, 40, 50}

# Upper bound on concurrent in-flight checks in one worker. Without this, a
# batch of slow or timing-out monitors would occupy every slot and starve the
# fast ones behind them.
MAX_CONCURRENT_CHECKS = 20


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, json_output=settings.ENV != "dev")

    # One client for the worker's lifetime, so connections are pooled and
    # reused across checks instead of being rebuilt per request.
    ctx["http_client"] = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=MAX_CONCURRENT_CHECKS * 2),
        headers={"User-Agent": "PingBoard/0.1 (+https://github.com/pingboard)"},
        # Checks must never be served from a cache — that would report a stale
        # response as a live one.
        trust_env=False,
    )
    logger.info("worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    client: httpx.AsyncClient | None = ctx.get("http_client")
    if client is not None:
        await client.aclose()
    await dispose_engine()
    logger.info("worker stopped")


class WorkerSettings:
    # ClassVar: ARQ reads these off the class, they are never per-instance.
    functions: ClassVar[list[Any]] = [run_monitor_check, deliver_notification]
    cron_jobs: ClassVar[list[Any]] = [
        cron(
            scheduler_tick,
            second=SCHEDULER_TICK_SECONDS,
            # The scheduler is a claim-and-enqueue pass; if one tick is still
            # running, skipping the next is correct — the work stays due.
            run_at_startup=True,
            max_tries=1,
        ),
        # A few minutes past the hour, so the hour being summarised is safely
        # closed and any in-flight checks for it have landed.
        cron(rollup_previous_hour, minute={5}, max_tries=2),
        # Daily, off-peak: pruning is I/O heavy and never urgent.
        cron(prune_old_checks, hour={4}, minute={20}, max_tries=1),
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = MAX_CONCURRENT_CHECKS
    job_timeout = 90
    # A failed check is already recorded as a failure; retrying would double
    # count it and hit the target again for no benefit. Notification delivery
    # overrides this per-job — webhooks do fail transiently.
    max_tries = 1
    retry_jobs = True
    keep_result = 60

    # ARQ reads this as a value, not a callable.
    redis_settings = RedisSettings.from_dsn(str(get_settings().REDIS_URL))
