"""Request and response bodies for incidents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.incidents.models import IncidentSeverity


class IncidentUpdateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


class IncidentUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    message: str
    created_by: UUID | None
    is_auto: bool
    created_at: datetime


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitor_id: UUID
    started_at: datetime
    resolved_at: datetime | None
    severity: IncidentSeverity
    cause: str | None
    created_at: datetime

    # Denormalised for display, so a list does not need an N+1 per row.
    monitor_name: str | None = None


class IncidentDetail(IncidentRead):
    updates: list[IncidentUpdateRead] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="Resolved manually.", min_length=1, max_length=2000)
