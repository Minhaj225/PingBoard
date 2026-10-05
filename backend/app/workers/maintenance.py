"""Scheduled maintenance jobs: hourly rollups and raw-data retention."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.monitors.rollups import previous_hour, prune_raw_checks, rollup_hour

logger = logging.getLogger(__name__)


async def rollup_previous_hour(ctx: dict[str, Any]) -> dict[str, int]:
    """Aggregate the most recent *closed* hour into `rollups_hourly`.

    Only a closed hour is rolled up: summarising the current one would write a
    partial row. The upsert makes a re-run harmless, so a retry after a crash
    simply recomputes.
    """
    hour = previous_hour(datetime.now(UTC))

    async with SessionLocal() as db:
        rows = await rollup_hour(db, hour_start=hour)

    logger.info("hourly rollup complete", extra={"hour": hour.isoformat(), "rows": rows})
    return {"hour_rows": rows}


async def prune_old_checks(ctx: dict[str, Any]) -> dict[str, int]:
    """Drop raw check rows that have already been rolled up.

    Retention is a deliberate trade: beyond the window, history stays available
    at hourly resolution via rollups, but individual probe results are gone.
    Keep `RAW_RETENTION_DAYS` high (or disable this job) if per-check forensics
    matter more than table size.
    """
    settings = get_settings()

    async with SessionLocal() as db:
        deleted = await prune_raw_checks(db, older_than_days=settings.RAW_RETENTION_DAYS)

    return {"deleted": deleted}
