"""Monitor and check-result models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin


class MonitorStatus(enum.StrEnum):
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"


monitor_status_enum = Enum(
    MonitorStatus,
    name="monitor_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Monitor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "monitors"
    __table_args__ = (
        # The scheduler's hot query is `WHERE is_active AND next_run_at <= now()`.
        # A partial index keeps only the rows that query can ever match, so
        # paused monitors cost nothing to skip and the index stays small.
        Index(
            "ix_monitors_due",
            "next_run_at",
            postgresql_where=text("is_active"),
        ),
    )

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, server_default="GET")
    interval_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5000")
    assertions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Maintained by the worker. `status` only flips to DOWN once
    # `consecutive_failures` reaches the flap-protection threshold, so a single
    # blip never raises an alarm.
    status: Mapped[MonitorStatus] = mapped_column(
        monitor_status_enum, nullable=False, server_default=MonitorStatus.UNKNOWN.value
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Monitor {self.name} {self.url}>"


class CheckResult(UUIDMixin, Base):
    """One HTTP probe. High-volume table — append-only, never updated."""

    __tablename__ = "check_results"
    # History is always read newest-first, so the index is ordered to match and
    # the planner can walk it without a sort.
    __table_args__ = (Index("ix_check_results_monitor_checked", "monitor_id", desc("checked_at")),)

    monitor_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    monitor: Mapped[Monitor] = relationship(lazy="raise")
