"""Incident lifecycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.incidents.models import Incident, IncidentSeverity, IncidentUpdate
from app.monitors.models import Monitor

logger = logging.getLogger(__name__)


class IncidentAlreadyResolved(Exception):
    """The incident is already closed."""


async def get_open_incident(db: AsyncSession, monitor_id: UUID) -> Incident | None:
    return await db.scalar(
        select(Incident).where(Incident.monitor_id == monitor_id, Incident.resolved_at.is_(None))
    )


async def open_incident(
    db: AsyncSession,
    *,
    monitor: Monitor,
    cause: str | None,
    severity: IncidentSeverity = IncidentSeverity.MAJOR,
) -> Incident | None:
    """Open an incident for `monitor`, or return `None` if one is already open.

    The partial unique index is the real guard: two workers can reach this at
    the same moment, and losing that race must be a no-op, not a 500.
    """
    existing = await get_open_incident(db, monitor.id)
    if existing is not None:
        return None

    incident = Incident(
        monitor_id=monitor.id,
        started_at=datetime.now(UTC),
        severity=severity,
        cause=cause,
    )
    db.add(incident)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info(
            "lost the race to open an incident; another worker got there first",
            extra={"monitor_id": str(monitor.id)},
        )
        return None

    db.add(
        IncidentUpdate(
            incident_id=incident.id,
            message=f"{monitor.name} is down. {cause or 'The check failed.'}",
            is_auto=True,
        )
    )
    await db.flush()
    return incident


async def resolve_incident(
    db: AsyncSession, incident: Incident, *, message: str, by: User | None = None
) -> Incident:
    if incident.resolved_at is not None:
        raise IncidentAlreadyResolved(str(incident.id))

    incident.resolved_at = datetime.now(UTC)
    db.add(
        IncidentUpdate(
            incident_id=incident.id,
            message=message,
            created_by=by.id if by else None,
            is_auto=by is None,
        )
    )
    await db.flush()
    return incident


async def auto_resolve(db: AsyncSession, monitor: Monitor) -> Incident | None:
    """Close the open incident for a monitor that just recovered."""
    incident = await get_open_incident(db, monitor.id)
    if incident is None:
        return None

    duration = datetime.now(UTC) - incident.started_at
    minutes = max(1, round(duration.total_seconds() / 60))
    return await resolve_incident(
        db,
        incident,
        message=f"{monitor.name} is responding normally again after about {minutes} min.",
    )


async def add_update(
    db: AsyncSession, incident: Incident, *, message: str, by: User
) -> IncidentUpdate:
    update = IncidentUpdate(incident_id=incident.id, message=message, created_by=by.id)
    db.add(update)
    await db.flush()
    return update


async def list_incidents(
    db: AsyncSession,
    *,
    org_id: UUID,
    status: str | None = None,
    monitor_id: UUID | None = None,
    limit: int = 50,
) -> list[Incident]:
    """Incidents for an org, newest first.

    Scoped by joining through `monitors`: there is no `org_id` on `incidents`,
    and deriving it from the monitor is what keeps tenants separated.
    """
    query = (
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Monitor.org_id == org_id)
    )

    if status == "open":
        query = query.where(Incident.resolved_at.is_(None))
    elif status == "resolved":
        query = query.where(Incident.resolved_at.is_not(None))
    if monitor_id is not None:
        query = query.where(Incident.monitor_id == monitor_id)

    query = query.order_by(Incident.started_at.desc()).limit(limit)
    return list(await db.scalars(query))


async def get_incident_for_org(
    db: AsyncSession, *, incident_id: UUID, org_id: UUID, with_updates: bool = False
) -> Incident | None:
    query = (
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Incident.id == incident_id, Monitor.org_id == org_id)
    )
    if with_updates:
        query = query.options(selectinload(Incident.updates))
    return await db.scalar(query)
