"""Incident endpoints."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession
from app.incidents import service
from app.incidents.schemas import (
    IncidentDetail,
    IncidentRead,
    IncidentUpdateCreate,
    IncidentUpdateRead,
    ResolveRequest,
)
from app.monitors.models import Monitor
from app.orgs.scope import OrgAdmin, OrgViewer
from app.workers.notify import incident_resolved, incident_update
from app.workers.queue import enqueue_notification

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead], summary="List incidents for an org")
async def list_incidents(
    db: DbSession,
    membership: OrgViewer,
    incident_status: Annotated[Literal["open", "resolved"] | None, Query(alias="status")] = None,
    monitor_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[IncidentRead]:
    incidents = await service.list_incidents(
        db,
        org_id=membership.org_id,
        status=incident_status,
        monitor_id=monitor_id,
        limit=limit,
    )
    if not incidents:
        return []

    # One extra query for all the names, rather than one per incident.
    names = dict(
        (
            await db.execute(
                select(Monitor.id, Monitor.name).where(
                    Monitor.id.in_({incident.monitor_id for incident in incidents})
                )
            )
        ).all()
    )

    return [
        IncidentRead.model_validate(incident).model_copy(
            update={"monitor_name": names.get(incident.monitor_id)}
        )
        for incident in incidents
    ]


@router.get(
    "/{incident_id}", response_model=IncidentDetail, summary="One incident with its timeline"
)
async def get_incident(
    incident_id: UUID,
    db: DbSession,
    membership: OrgViewer,
) -> IncidentDetail:
    incident = await service.get_incident_for_org(
        db, incident_id=incident_id, org_id=membership.org_id, with_updates=True
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    monitor = await db.get(Monitor, incident.monitor_id)
    detail = IncidentDetail.model_validate(incident)
    return detail.model_copy(
        update={
            "monitor_name": monitor.name if monitor else None,
            "updates": [IncidentUpdateRead.model_validate(u) for u in incident.updates],
        }
    )


@router.post(
    "/{incident_id}/updates",
    response_model=IncidentUpdateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post an update to an incident's timeline",
)
async def post_update(
    incident_id: UUID,
    payload: IncidentUpdateCreate,
    db: DbSession,
    user: CurrentUser,
    membership: OrgAdmin,
) -> IncidentUpdateRead:
    incident = await service.get_incident_for_org(
        db,
        incident_id=incident_id,
        org_id=membership.org_id,
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    update = await service.add_update(db, incident, message=payload.message, by=user)
    monitor = await db.get(Monitor, incident.monitor_id)
    await db.commit()

    if monitor is not None:
        await enqueue_notification(
            str(monitor.org_id), incident_update(monitor.name, monitor.url, payload.message)
        )

    return IncidentUpdateRead.model_validate(update)


@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentDetail,
    summary="Resolve an incident manually",
)
async def resolve(
    incident_id: UUID,
    payload: ResolveRequest,
    db: DbSession,
    user: CurrentUser,
    membership: OrgAdmin,
) -> IncidentDetail:
    incident = await service.get_incident_for_org(
        db,
        incident_id=incident_id,
        org_id=membership.org_id,
    )
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    try:
        await service.resolve_incident(db, incident, message=payload.message, by=user)
    except service.IncidentAlreadyResolved as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This incident is already resolved"
        ) from exc

    monitor = await db.get(Monitor, incident.monitor_id)
    await db.commit()
    await db.refresh(incident, ["updates"])

    if monitor is not None:
        await enqueue_notification(
            str(monitor.org_id), incident_resolved(monitor.name, monitor.url, payload.message)
        )

    detail = IncidentDetail.model_validate(incident)
    return detail.model_copy(
        update={
            "monitor_name": monitor.name if monitor else None,
            "updates": [IncidentUpdateRead.model_validate(u) for u in incident.updates],
        }
    )
