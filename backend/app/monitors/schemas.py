"""Request and response bodies for the monitor endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.monitors.models import MonitorStatus

HttpMethod = Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

MIN_INTERVAL_S = 30
MAX_INTERVAL_S = 86_400
MIN_TIMEOUT_MS = 100
MAX_TIMEOUT_MS = 60_000


class Assertions(BaseModel):
    """What must hold for a check to count as `ok`.

    An empty object means "any 2xx/3xx response passes". This exact shape is the
    contract shared by the checker, the API and the frontend's form.
    """

    model_config = ConfigDict(extra="forbid")

    status_code: int | None = Field(default=None, ge=100, le=599)
    max_latency_ms: int | None = Field(default=None, ge=1, le=MAX_TIMEOUT_MS)
    body_contains: str | None = Field(default=None, min_length=1, max_length=500)
    body_not_contains: str | None = Field(default=None, min_length=1, max_length=500)


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    method: HttpMethod = "GET"
    interval_s: int = Field(default=60, ge=MIN_INTERVAL_S, le=MAX_INTERVAL_S)
    timeout_ms: int = Field(default=5_000, ge=MIN_TIMEOUT_MS, le=MAX_TIMEOUT_MS)
    assertions: Assertions = Field(default_factory=Assertions)

    @field_validator("url")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class MonitorUpdate(BaseModel):
    """PATCH body. Every field optional; omitted fields are left untouched."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    url: Annotated[str, Field(min_length=1, max_length=2048)] | None = None
    method: HttpMethod | None = None
    interval_s: Annotated[int, Field(ge=MIN_INTERVAL_S, le=MAX_INTERVAL_S)] | None = None
    timeout_ms: Annotated[int, Field(ge=MIN_TIMEOUT_MS, le=MAX_TIMEOUT_MS)] | None = None
    assertions: Assertions | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class MonitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    url: str
    method: str
    interval_s: int
    timeout_ms: int
    assertions: Assertions
    is_active: bool
    next_run_at: datetime
    created_at: datetime
    status: MonitorStatus
    consecutive_failures: int
    last_checked_at: datetime | None


class CheckResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitor_id: UUID
    checked_at: datetime
    ok: bool
    status_code: int | None
    latency_ms: int | None
    error: str | None


class CheckPage(BaseModel):
    """Cursor-paginated check history.

    The cursor is the `checked_at` of the last row, which pairs with the
    `(monitor_id, checked_at)` index — unlike OFFSET, it stays fast deep into
    the history.
    """

    items: list[CheckResultRead]
    next_cursor: datetime | None = None
