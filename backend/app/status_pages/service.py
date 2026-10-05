"""Status page persistence and public-view assembly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.incidents.models import Incident, IncidentUpdate
from app.monitors.models import Monitor, MonitorStatus
from app.status_pages.models import StatusPage, status_page_monitors
from app.status_pages.queries import DEFAULT_UPTIME_DAYS, daily_uptime
from app.status_pages.schemas import (
    PublicDay,
    PublicIncident,
    PublicIncidentUpdate,
    PublicMonitor,
    PublicStatusPage,
)

# How far back the public page lists incidents.
PUBLIC_INCIDENT_DAYS = 30

# Below this, a monitor that is technically "up" is still shown as degraded,
# because a page claiming "operational" after a rough week is misleading.
DEGRADED_UPTIME_PCT = 99.0


class SlugTaken(Exception):
    """Another status page already uses this slug."""


async def create_page(
    db: AsyncSession,
    *,
    org_id: UUID,
    title: str,
    slug: str,
    description: str | None,
    monitor_ids: list[UUID],
) -> StatusPage:
    if await db.scalar(select(StatusPage.id).where(StatusPage.slug == slug)):
        raise SlugTaken(slug)

    page = StatusPage(org_id=org_id, title=title, slug=slug, description=description)
    db.add(page)
    await db.flush()
    await set_monitors(db, page, monitor_ids, org_id=org_id)
    return page


async def set_monitors(
    db: AsyncSession, page: StatusPage, monitor_ids: list[UUID], *, org_id: UUID
) -> None:
    """Replace the page's monitor set.

    Ids are filtered through the owning org: a page must not be able to publish
    a monitor belonging to someone else just by guessing its id.
    """
    await db.execute(
        delete(status_page_monitors).where(status_page_monitors.c.status_page_id == page.id)
    )
    if not monitor_ids:
        return

    owned = set(
        await db.scalars(
            select(Monitor.id).where(Monitor.id.in_(monitor_ids), Monitor.org_id == org_id)
        )
    )
    if owned:
        await db.execute(
            insert(status_page_monitors),
            [{"status_page_id": page.id, "monitor_id": mid} for mid in owned],
        )


async def get_monitor_ids(db: AsyncSession, page_id: UUID) -> list[UUID]:
    return list(
        await db.scalars(
            select(status_page_monitors.c.monitor_id).where(
                status_page_monitors.c.status_page_id == page_id
            )
        )
    )


async def list_pages(db: AsyncSession, org_id: UUID) -> list[StatusPage]:
    return list(
        await db.scalars(
            select(StatusPage).where(StatusPage.org_id == org_id).order_by(StatusPage.created_at)
        )
    )


async def get_page_for_org(db: AsyncSession, *, page_id: UUID, org_id: UUID) -> StatusPage | None:
    return await db.scalar(
        select(StatusPage).where(StatusPage.id == page_id, StatusPage.org_id == org_id)
    )


# --- Public view ------------------------------------------------------------


async def build_public_view(db: AsyncSession, slug: str) -> PublicStatusPage | None:
    """Assemble the anonymous view of a page, or `None` if it isn't published."""
    page = await db.scalar(
        select(StatusPage)
        .where(StatusPage.slug == slug, StatusPage.is_published.is_(True))
        .options(selectinload(StatusPage.monitors))
    )
    if page is None:
        return None

    monitors = page.monitors
    public_monitors: list[PublicMonitor] = []

    for monitor in monitors:
        history = await daily_uptime(db, monitor.id, days=DEFAULT_UPTIME_DAYS)
        measured = [day for day in history if day.checks > 0]
        total_checks = sum(day.checks for day in measured)
        total_failures = sum(day.failures for day in measured)
        uptime_90d = (
            round(100.0 * (total_checks - total_failures) / total_checks, 2)
            if total_checks
            else 0.0
        )

        public_monitors.append(
            PublicMonitor(
                name=monitor.name,
                status=_public_status(monitor.status, uptime_90d, total_checks),
                uptime_90d=uptime_90d,
                days=[
                    PublicDay(date=day.day, state=day.state, uptime_pct=day.uptime_pct)
                    for day in history
                ],
            )
        )

    incidents = await _public_incidents(
        db, [m.id for m in monitors], {m.id: m.name for m in monitors}
    )

    return PublicStatusPage(
        title=page.title,
        description=page.description,
        overall=_overall(public_monitors),
        monitors=public_monitors,
        incidents=incidents,
        updated_at=datetime.now(UTC),
    )


def _public_status(status: MonitorStatus, uptime_90d: float, total_checks: int) -> str:
    if total_checks == 0 or status is MonitorStatus.UNKNOWN:
        return "unknown"
    if status is MonitorStatus.DOWN:
        return "down"
    return "degraded" if uptime_90d < DEGRADED_UPTIME_PCT else "operational"


def _overall(monitors: list[PublicMonitor]) -> str:
    """The worst state on the page wins — a banner must not under-report."""
    states = {monitor.status for monitor in monitors}
    for state in ("down", "degraded", "unknown"):
        if state in states:
            return state
    return "operational" if monitors else "unknown"


async def _public_incidents(
    db: AsyncSession, monitor_ids: list[UUID], names: dict[UUID, str]
) -> list[PublicIncident]:
    if not monitor_ids:
        return []

    since = datetime.now(UTC) - timedelta(days=PUBLIC_INCIDENT_DAYS)
    incidents = list(
        await db.scalars(
            select(Incident)
            .where(Incident.monitor_id.in_(monitor_ids), Incident.started_at >= since)
            .options(selectinload(Incident.updates))
            .order_by(Incident.started_at.desc())
            .limit(50)
        )
    )

    return [
        PublicIncident(
            monitor_name=names.get(incident.monitor_id, "Service"),
            started_at=incident.started_at,
            resolved_at=incident.resolved_at,
            severity=incident.severity.value,
            updates=[
                PublicIncidentUpdate(message=update.message, created_at=update.created_at)
                for update in _visible_updates(incident.updates)
            ],
        )
        for incident in incidents
    ]


def _visible_updates(updates: list[IncidentUpdate]) -> list[IncidentUpdate]:
    """Everything on the timeline is already written for an audience.

    Kept as a seam so a future "internal note" flag has one place to filter.
    """
    return sorted(updates, key=lambda update: update.created_at)
