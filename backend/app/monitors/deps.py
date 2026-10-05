"""Monitor-scoped dependencies.

Every monitor route resolves the monitor *through* the caller's membership, so
a monitor id from another organization simply does not exist as far as the
request is concerned.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status

from app.auth.deps import CurrentUser, DbSession
from app.auth.models import User
from app.monitors import service
from app.monitors.models import Monitor
from app.orgs.deps import get_membership
from app.orgs.models import MemberRole, Membership

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")


async def _resolve(
    monitor_id: UUID, user: User, db: DbSession, minimum: MemberRole
) -> tuple[Monitor, Membership]:
    monitor = await db.get(Monitor, monitor_id)
    if monitor is None:
        raise _NOT_FOUND

    # Authorization is derived from the monitor's own org, never from a value
    # the caller supplied.
    membership = await get_membership(db, monitor.org_id, user)
    if membership is None:
        raise _NOT_FOUND

    if not membership.role.covers(minimum):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires the {minimum.value} role or higher",
        )
    return monitor, membership


async def get_readable_monitor(
    db: DbSession,
    user: CurrentUser,
    monitor_id: Annotated[UUID, Path()],
) -> Monitor:
    monitor, _ = await _resolve(monitor_id, user, db, MemberRole.VIEWER)
    return monitor


async def get_writable_monitor(
    db: DbSession,
    user: CurrentUser,
    monitor_id: Annotated[UUID, Path()],
) -> Monitor:
    monitor, _ = await _resolve(monitor_id, user, db, MemberRole.ADMIN)
    return monitor


ReadableMonitor = Annotated[Monitor, Depends(get_readable_monitor)]
WritableMonitor = Annotated[Monitor, Depends(get_writable_monitor)]

__all__ = ["ReadableMonitor", "WritableMonitor", "service"]
