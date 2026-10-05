"""Hourly rollup table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RollupHourly(Base):
    """One row per monitor per hour.

    The composite primary key `(monitor_id, hour)` is what makes the rollup job
    idempotent: re-running an hour upserts rather than duplicating.
    """

    __tablename__ = "rollups_hourly"

    monitor_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("monitors.id", ondelete="CASCADE"), primary_key=True
    )
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    checks: Mapped[int] = mapped_column(Integer, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
