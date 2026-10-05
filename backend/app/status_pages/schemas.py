"""Status page schemas.

The public schemas at the bottom are deliberately **separate** from the admin
ones and from `MonitorRead`. Reusing an internal schema on an unauthenticated
endpoint is how target URLs, org ids and assertion details leak; here the public
shape is written out field by field, so anything added to a monitor later stays
private until someone deliberately exposes it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


# --- Admin ----------------------------------------------------------------


class StatusPageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=500)
    monitor_ids: list[UUID] = Field(default_factory=list)


class StatusPageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=500)
    is_published: bool | None = None
    monitor_ids: list[UUID] | None = None


class StatusPageRead(BaseModel):
    """Admin view — safe to include ids, since the caller is a member."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    slug: str
    title: str
    description: str | None
    is_published: bool
    created_at: datetime
    monitor_ids: list[UUID] = Field(default_factory=list)
    public_url: str


# --- Public (no auth) -------------------------------------------------------


class PublicDay(BaseModel):
    """One cell of the uptime bar."""

    date: date
    state: Literal["up", "degraded", "down", "no_data"]
    uptime_pct: float


class PublicMonitor(BaseModel):
    """What an anonymous visitor may see about a monitor.

    Note what is absent: the target `url`, the `org_id`, the assertions, the
    interval, and the monitor's real id. A visitor gets a display name, a
    traffic light, and a history bar.
    """

    name: str
    status: Literal["operational", "degraded", "down", "unknown"]
    uptime_90d: float
    days: list[PublicDay]


class PublicIncident(BaseModel):
    """An incident as shown publicly — no internal ids, no raw check errors."""

    monitor_name: str
    started_at: datetime
    resolved_at: datetime | None
    severity: str
    updates: list[PublicIncidentUpdate]


class PublicIncidentUpdate(BaseModel):
    message: str
    created_at: datetime


class PublicStatusPage(BaseModel):
    title: str
    description: str | None
    overall: Literal["operational", "degraded", "down", "unknown"]
    monitors: list[PublicMonitor]
    incidents: list[PublicIncident]
    updated_at: datetime


PublicIncident.model_rebuild()
