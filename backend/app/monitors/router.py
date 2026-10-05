"""Monitor endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth.deps import DbSession
from app.core.ratelimit import write_rate_limit
from app.monitors import service
from app.monitors.checker import run_check
from app.monitors.deps import ReadableMonitor, WritableMonitor
from app.monitors.schemas import (
    CheckPage,
    CheckResultRead,
    MonitorCreate,
    MonitorRead,
    MonitorUpdate,
)
from app.orgs.api_key_deps import ScriptableAdmin
from app.orgs.scope import OrgViewer

router = APIRouter(prefix="/monitors", tags=["monitors"])

DEFAULT_PAGE_SIZE = 50


@router.post(
    "",
    response_model=MonitorRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Create a monitor (accepts a bearer token or an X-API-Key header)",
)
async def create_monitor(
    payload: MonitorCreate,
    db: DbSession,
    principal: ScriptableAdmin,
) -> MonitorRead:
    """Scriptable: a CI job can create monitors with an API key and no session."""
    try:
        monitor = await service.create_monitor(db, org_id=principal.org_id, payload=payload)
    except service.UnsafeUrl as exc:
        # 422, not 400: the URL is syntactically fine but not an allowed target.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        ) from exc

    await db.commit()
    return MonitorRead.model_validate(monitor)


@router.get("", response_model=list[MonitorRead], summary="List an organization's monitors")
async def list_monitors(db: DbSession, membership: OrgViewer) -> list[MonitorRead]:
    monitors = await service.list_monitors(db, membership.org_id)
    return [MonitorRead.model_validate(monitor) for monitor in monitors]


@router.get("/{monitor_id}", response_model=MonitorRead, summary="Fetch one monitor")
async def get_monitor(monitor: ReadableMonitor) -> MonitorRead:
    return MonitorRead.model_validate(monitor)


@router.patch("/{monitor_id}", response_model=MonitorRead, summary="Update a monitor")
async def update_monitor(
    payload: MonitorUpdate,
    db: DbSession,
    monitor: WritableMonitor,
) -> MonitorRead:
    try:
        updated = await service.update_monitor(db, monitor, payload)
    except service.UnsafeUrl as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        ) from exc

    await db.commit()
    return MonitorRead.model_validate(updated)


@router.delete(
    "/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a monitor and its check history",
)
async def delete_monitor(db: DbSession, monitor: WritableMonitor) -> Response:
    await db.delete(monitor)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{monitor_id}/run-now",
    response_model=CheckResultRead,
    summary="Run one check immediately",
)
async def run_now(db: DbSession, monitor: WritableMonitor) -> CheckResultRead:
    """Probe synchronously and persist the result.

    Phase 3 moves scheduled checks onto a worker; this endpoint stays as the
    manual "test it now" path, which is worth keeping synchronous so the user
    sees the outcome straight away.
    """
    # Guard again at execution time: DNS may have changed since the monitor was
    # saved, which is exactly the rebinding case the guard exists for.
    try:
        await service.validate_url(monitor.url)
    except service.UnsafeUrl as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        ) from exc

    async with httpx.AsyncClient() as client:
        outcome = await run_check(monitor, client)

    result = await service.record_check(db, monitor=monitor, outcome=outcome)
    await db.commit()
    return CheckResultRead.model_validate(result)


@router.get(
    "/{monitor_id}/checks",
    response_model=CheckPage,
    summary="Paginated check history, newest first",
)
async def list_checks(
    db: DbSession,
    monitor: ReadableMonitor,
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_CHECK_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: Annotated[datetime | None, Query()] = None,
) -> CheckPage:
    results = await service.list_checks(
        db, monitor_id=monitor.id, since=since, until=until, limit=limit, cursor=cursor
    )
    # A full page implies there may be more; a short page is definitively the end.
    next_cursor = results[-1].checked_at if len(results) == limit else None
    return CheckPage(
        items=[CheckResultRead.model_validate(row) for row in results],
        next_cursor=next_cursor,
    )


@router.post("/{monitor_id}/pause", response_model=MonitorRead, summary="Pause a monitor")
async def pause_monitor(db: DbSession, monitor: WritableMonitor) -> MonitorRead:
    updated = await service.set_active(db, monitor, is_active=False)
    await db.commit()
    return MonitorRead.model_validate(updated)


@router.post("/{monitor_id}/resume", response_model=MonitorRead, summary="Resume a monitor")
async def resume_monitor(db: DbSession, monitor: WritableMonitor) -> MonitorRead:
    updated = await service.set_active(db, monitor, is_active=True)
    await db.commit()
    return MonitorRead.model_validate(updated)
