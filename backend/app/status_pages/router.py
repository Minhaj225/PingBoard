"""Status page endpoints — admin (authenticated) and public (not)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.auth.deps import DbSession
from app.core.cache import (
    PUBLIC_STATUS_TTL_S,
    UPTIME_TTL_S,
    cached_json,
    public_status_key,
    uptime_key,
)
from app.core.config import Settings, get_settings
from app.core.ratelimit import public_rate_limit
from app.monitors.deps import ReadableMonitor
from app.monitors.rollups import uptime_from_rollups
from app.orgs.scope import OrgAdmin, OrgViewer
from app.status_pages import service
from app.status_pages.models import StatusPage
from app.status_pages.queries import WINDOWS
from app.status_pages.schemas import (
    PublicStatusPage,
    StatusPageCreate,
    StatusPageRead,
    StatusPageUpdate,
)

router = APIRouter(prefix="/status-pages", tags=["status pages"])

# Mounted separately so it is impossible to accidentally inherit an auth
# dependency added to the admin router above.
public_router = APIRouter(prefix="/public", tags=["public"])


def _to_read(page: StatusPage, monitor_ids: list[UUID], settings: Settings) -> StatusPageRead:
    """Build the admin view explicitly.

    `public_url` and `monitor_ids` are derived, not columns, so the model is
    constructed field by field rather than validated off the ORM object and
    patched afterwards.
    """
    return StatusPageRead(
        id=page.id,
        org_id=page.org_id,
        slug=page.slug,
        title=page.title,
        description=page.description,
        is_published=page.is_published,
        created_at=page.created_at,
        monitor_ids=monitor_ids,
        public_url=f"{settings.FRONTEND_URL}/status/{page.slug}",
    )


@router.post(
    "",
    response_model=StatusPageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a status page",
)
async def create_status_page(
    payload: StatusPageCreate, db: DbSession, membership: OrgAdmin
) -> StatusPageRead:
    try:
        page = await service.create_page(
            db,
            org_id=membership.org_id,
            title=payload.title,
            slug=payload.slug,
            description=payload.description,
            monitor_ids=payload.monitor_ids,
        )
        await db.commit()
    except service.SlugTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That slug is already taken"
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That slug is already taken"
        ) from exc

    ids = await service.get_monitor_ids(db, page.id)
    return _to_read(page, ids, get_settings())


@router.get("", response_model=list[StatusPageRead], summary="List status pages")
async def list_status_pages(db: DbSession, membership: OrgViewer) -> list[StatusPageRead]:
    settings = get_settings()
    pages = await service.list_pages(db, membership.org_id)
    return [_to_read(page, await service.get_monitor_ids(db, page.id), settings) for page in pages]


@router.patch("/{page_id}", response_model=StatusPageRead, summary="Update a status page")
async def update_status_page(
    page_id: UUID, payload: StatusPageUpdate, db: DbSession, membership: OrgAdmin
) -> StatusPageRead:
    page = await service.get_page_for_org(db, page_id=page_id, org_id=membership.org_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status page not found")

    changes = payload.model_dump(exclude_unset=True)
    monitor_ids = changes.pop("monitor_ids", None)

    for field, value in changes.items():
        setattr(page, field, value)

    if monitor_ids is not None:
        await service.set_monitors(db, page, monitor_ids, org_id=membership.org_id)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That slug is already taken"
        ) from exc

    ids = await service.get_monitor_ids(db, page.id)
    return _to_read(page, ids, get_settings())


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a status page")
async def delete_status_page(page_id: UUID, db: DbSession, membership: OrgAdmin) -> Response:
    page = await service.get_page_for_org(db, page_id=page_id, org_id=membership.org_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status page not found")

    await db.delete(page)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Uptime (authenticated) -------------------------------------------------

uptime_router = APIRouter(prefix="/monitors", tags=["monitors"])


@uptime_router.get("/{monitor_id}/uptime", summary="Uptime and p95 latency over a window")
async def monitor_uptime(
    db: DbSession,
    response: Response,
    monitor: ReadableMonitor,
    window: Annotated[str, Query(pattern="^(24h|7d|30d|90d)$")] = "24h",
) -> dict[str, float | int | str]:
    """Uptime over a window, read from hourly rollups rather than raw rows.

    Rollups cover every closed hour; the still-open hour is added from
    `check_results`, so the figure stays current without scanning the window.
    """
    since = datetime.now(UTC) - WINDOWS[window]

    async def compute() -> dict[str, float | int | str]:
        result = await uptime_from_rollups(db, monitor.id, since=since)
        return {
            "window": window,
            "checks": result.checks,
            "failures": result.failures,
            "uptime_pct": result.uptime_pct,
            "p95_ms": result.p95_ms,
            "source": result.source,
        }

    payload, was_cached = await cached_json(
        uptime_key(str(monitor.id), window), UPTIME_TTL_S, compute
    )
    response.headers["X-Cache"] = "HIT" if was_cached else "MISS"
    # `cached_json` round-trips through JSON, so the static type is lost.
    return cast(dict[str, float | int | str], payload)


# --- Public (no auth) -------------------------------------------------------


@public_router.get(
    "/status/{slug}",
    response_model=PublicStatusPage,
    dependencies=[Depends(public_rate_limit)],
    summary="Public status page (no authentication)",
)
async def public_status_page(
    db: DbSession,
    response: Response,
    slug: Annotated[str, Path(max_length=80)],
) -> PublicStatusPage:
    """Anonymous view of a published status page.

    This route takes **no** auth dependency and returns a schema written for
    this endpoint alone — never `MonitorRead` — so no internal field can leak
    by being added to a model later.
    """

    async def compute() -> dict[str, object] | None:
        built = await service.build_public_view(db, slug)
        return built.model_dump(mode="json") if built else None

    payload, was_cached = await cached_json(public_status_key(slug), PUBLIC_STATUS_TTL_S, compute)

    if payload is None:
        # Same response whether the page does not exist or is unpublished, so
        # the endpoint cannot be used to enumerate private slugs. A miss is not
        # cached, so publishing a page takes effect immediately.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Status page not found")

    response.headers["Cache-Control"] = f"public, max-age={PUBLIC_STATUS_TTL_S}"
    response.headers["X-Cache"] = "HIT" if was_cached else "MISS"
    return PublicStatusPage.model_validate(payload)
