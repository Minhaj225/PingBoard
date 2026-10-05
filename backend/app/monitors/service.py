"""Monitor persistence and queries."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitors.checker import CheckOutcome
from app.monitors.models import CheckResult, Monitor
from app.monitors.schemas import MonitorCreate, MonitorUpdate
from app.monitors.ssrf import check_url

# Cap how far back a history query may scan, so one request cannot ask the
# database for a year of rows.
MAX_CHECK_PAGE_SIZE = 200


class UnsafeUrl(Exception):
    """The URL failed the SSRF guard."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def validate_url(url: str) -> None:
    """Run the SSRF guard off the event loop (it performs a DNS lookup)."""
    result = await asyncio.to_thread(check_url, url)
    if not result:
        raise UnsafeUrl(result.reason)


async def get_monitor(db: AsyncSession, org_id: UUID, monitor_id: UUID) -> Monitor | None:
    """Always filtered by `org_id`: an id alone must never grant access."""
    return await db.scalar(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.org_id == org_id)
    )


async def list_monitors(db: AsyncSession, org_id: UUID) -> list[Monitor]:
    result = await db.scalars(
        select(Monitor).where(Monitor.org_id == org_id).order_by(Monitor.created_at.desc())
    )
    return list(result)


async def create_monitor(db: AsyncSession, *, org_id: UUID, payload: MonitorCreate) -> Monitor:
    await validate_url(payload.url)

    monitor = Monitor(
        org_id=org_id,
        name=payload.name,
        url=payload.url,
        method=payload.method,
        interval_s=payload.interval_s,
        timeout_ms=payload.timeout_ms,
        assertions=payload.assertions.model_dump(exclude_none=True),
        is_active=True,
        # Due immediately, so a new monitor reports within one scheduler tick.
        next_run_at=datetime.now(UTC),
    )
    db.add(monitor)
    await db.flush()
    return monitor


async def update_monitor(db: AsyncSession, monitor: Monitor, payload: MonitorUpdate) -> Monitor:
    changes = payload.model_dump(exclude_unset=True)

    # Re-check on update, not only on create: otherwise a monitor could be
    # created against a public URL and then repointed at an internal one.
    if "url" in changes and changes["url"] != monitor.url:
        await validate_url(changes["url"])

    if "assertions" in changes and payload.assertions is not None:
        changes["assertions"] = payload.assertions.model_dump(exclude_none=True)

    for field, value in changes.items():
        setattr(monitor, field, value)

    # A shortened interval should take effect now, not after the old one elapses.
    if "interval_s" in changes:
        monitor.next_run_at = min(
            monitor.next_run_at, datetime.now(UTC) + timedelta(seconds=monitor.interval_s)
        )

    await db.flush()
    return monitor


async def set_active(db: AsyncSession, monitor: Monitor, *, is_active: bool) -> Monitor:
    monitor.is_active = is_active
    if is_active:
        # Resume promptly rather than waiting out the interval it slept through.
        monitor.next_run_at = datetime.now(UTC)
    await db.flush()
    return monitor


async def record_check(db: AsyncSession, *, monitor: Monitor, outcome: CheckOutcome) -> CheckResult:
    result = CheckResult(
        monitor_id=monitor.id,
        checked_at=datetime.now(UTC),
        ok=outcome.ok,
        status_code=outcome.status_code,
        latency_ms=outcome.latency_ms,
        error=outcome.error,
    )
    db.add(result)
    await db.flush()
    return result


async def list_checks(
    db: AsyncSession,
    *,
    monitor_id: UUID,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    cursor: datetime | None = None,
) -> list[CheckResult]:
    """Newest first, cursor-paginated on `checked_at`."""
    query = select(CheckResult).where(CheckResult.monitor_id == monitor_id)

    if since is not None:
        query = query.where(CheckResult.checked_at >= since)
    if until is not None:
        query = query.where(CheckResult.checked_at <= until)
    if cursor is not None:
        query = query.where(CheckResult.checked_at < cursor)

    query = query.order_by(CheckResult.checked_at.desc()).limit(min(limit, MAX_CHECK_PAGE_SIZE))
    return list(await db.scalars(query))
