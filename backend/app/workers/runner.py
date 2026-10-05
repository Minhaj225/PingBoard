"""The scheduler loop and the per-monitor check job.

Two responsibilities, deliberately split:

* `claim_due_monitors` finds work and marks it as taken, atomically.
* `run_monitor_check` executes one check and folds the result into the monitor.

The split is what makes the system safe to run as more than one worker, and it
keeps the slow part (an outbound HTTP request that may sit for seconds) out of
the transaction that decides what to work on.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Import every model so cross-module foreign keys (monitors -> organizations)
# can resolve; the worker otherwise only loads the monitor models.
from app.core import models_registry  # noqa: F401
from app.core.db import SessionLocal
from app.incidents import service as incidents
from app.monitors.checker import CheckOutcome, run_check
from app.monitors.models import Monitor, MonitorStatus
from app.monitors.service import UnsafeUrl, record_check, validate_url
from app.workers.notify import incident_opened, incident_resolved
from app.workers.schedule import DEFAULT_FAILURE_THRESHOLD, apply_check_outcome, next_run_after

logger = logging.getLogger(__name__)

# How many monitors one scheduler tick will claim. Bounds the burst a single
# tick can put on the queue when a large backlog comes due at once.
CLAIM_BATCH_SIZE = 100


async def claim_due_monitors(
    db: AsyncSession, *, now: datetime, limit: int = CLAIM_BATCH_SIZE
) -> list[UUID]:
    """Atomically claim the monitors that are due, returning their ids.

    `SKIP LOCKED` is what makes this safe to run in several workers at once:
    each row is handed to exactly one of them, and a row another worker already
    holds is passed over rather than waited on.

    `next_run_at` is advanced *as part of the claim*, before any check runs. If
    the worker then crashes mid-check, the monitor simply misses one round
    instead of being re-claimed in a tight loop — losing a data point is far
    cheaper than hammering someone's server.
    """
    due = (
        select(Monitor.id, Monitor.next_run_at, Monitor.interval_s)
        .where(Monitor.is_active.is_(True), Monitor.next_run_at <= now)
        .order_by(Monitor.next_run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = (await db.execute(due)).all()
    if not rows:
        return []

    for monitor_id, previous_run_at, interval_s in rows:
        await db.execute(
            update(Monitor)
            .where(Monitor.id == monitor_id)
            .values(
                next_run_at=next_run_after(
                    previous_run_at=previous_run_at, interval_s=interval_s, now=now
                )
            )
        )

    await db.commit()
    return [row[0] for row in rows]


async def scheduler_tick(ctx: dict[str, Any]) -> int:
    """Claim due monitors and enqueue a check job for each. Returns the count."""
    redis = ctx["redis"]
    now = datetime.now(UTC)

    async with SessionLocal() as db:
        monitor_ids = await claim_due_monitors(db, now=now)

    for monitor_id in monitor_ids:
        # A per-monitor-per-slot job id makes the enqueue idempotent: if two
        # schedulers somehow claim the same slot, ARQ keeps only one job.
        await redis.enqueue_job(
            "run_monitor_check",
            str(monitor_id),
            _job_id=f"check:{monitor_id}:{int(now.timestamp())}",
        )

    if monitor_ids:
        logger.info("scheduler enqueued checks", extra={"count": len(monitor_ids)})
    return len(monitor_ids)


async def run_monitor_check(ctx: dict[str, Any], monitor_id: str) -> dict[str, Any]:
    """Probe one monitor, persist the result, and update its status."""
    client: httpx.AsyncClient = ctx["http_client"]

    async with SessionLocal() as db:
        monitor = await db.get(Monitor, UUID(monitor_id))

        if monitor is None:
            logger.info("skipping check for deleted monitor", extra={"monitor_id": monitor_id})
            return {"skipped": "deleted"}

        if not monitor.is_active:
            # Paused between the claim and the dequeue.
            return {"skipped": "paused"}

        # Re-validate at execution time: DNS can change after the monitor was
        # saved, which is precisely the rebinding case the guard exists for.
        try:
            await validate_url(monitor.url)
        except UnsafeUrl as exc:
            # Recorded as a failed check rather than raised: the monitor's owner
            # should see *why* it stopped working, and a raise would just retry.
            return await _persist(
                db, monitor, ctx=ctx, ok=False, error=f"Blocked target: {exc.reason}"
            )

        outcome = await run_check(monitor, client)
        return await _persist(
            db,
            monitor,
            ctx=ctx,
            ok=outcome.ok,
            status_code=outcome.status_code,
            latency_ms=outcome.latency_ms,
            error=outcome.error,
        )


async def _persist(
    db: AsyncSession,
    monitor: Monitor,
    *,
    ctx: dict[str, Any],
    ok: bool,
    status_code: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Write the check result and fold it into the monitor's status."""
    outcome = CheckOutcome(ok=ok, status_code=status_code, latency_ms=latency_ms, error=error)
    await record_check(db, monitor=monitor, outcome=outcome)

    transition = apply_check_outcome(
        current_status=monitor.status.value,
        consecutive_failures=monitor.consecutive_failures,
        ok=ok,
        threshold=DEFAULT_FAILURE_THRESHOLD,
    )

    monitor.status = MonitorStatus(transition.status)
    monitor.consecutive_failures = transition.consecutive_failures
    monitor.last_checked_at = datetime.now(UTC)
    await db.commit()

    # Incidents are opened and closed on the status *edge* only, so a monitor
    # that stays down does not reopen (or re-notify) on every subsequent check.
    if transition.went_down:
        logger.warning(
            "monitor went down",
            extra={"monitor_id": str(monitor.id), "url": monitor.url, "error": error},
        )
        incident = await incidents.open_incident(db, monitor=monitor, cause=error)
        await db.commit()
        if incident is not None:
            await _enqueue_notification(
                ctx, monitor, incident_opened(monitor.name, monitor.url, error)
            )

    elif transition.recovered:
        logger.info("monitor recovered", extra={"monitor_id": str(monitor.id)})
        incident = await incidents.auto_resolve(db, monitor)
        await db.commit()
        if incident is not None:
            message = f"{monitor.name} is responding normally again."
            await _enqueue_notification(
                ctx, monitor, incident_resolved(monitor.name, monitor.url, message)
            )

    return {
        "ok": ok,
        "status": transition.status,
        "went_down": transition.went_down,
        "recovered": transition.recovered,
    }


async def _enqueue_notification(
    ctx: dict[str, Any], monitor: Monitor, payload: dict[str, Any]
) -> None:
    """Hand delivery to the queue — never call a webhook from the check path.

    A failure to enqueue must not fail the check: the check result itself is
    already safely written, and losing a notification is the lesser harm.
    """
    try:
        await ctx["redis"].enqueue_job("deliver_notification", str(monitor.org_id), payload)
    except Exception:
        logger.exception("could not enqueue notification", extra={"monitor_id": str(monitor.id)})
