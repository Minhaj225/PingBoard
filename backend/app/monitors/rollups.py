"""Hourly rollups and raw-data retention.

Raw `check_results` grow without bound: one 30-second monitor is ~2,880 rows a
day. Reading a 30-day uptime figure from raw rows means scanning ~86,000 of them
per monitor; reading it from rollups means 720.

The aggregation runs in SQL. The `GROUP BY` here is the one thing worth reading
closely — a wrong grouping produces plausible-looking numbers that are quietly
incorrect, which is far worse than an obvious error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Keep raw rows for this long. Rollups are retained indefinitely, so history
# older than this stays available at hourly resolution.
RAW_RETENTION_DAYS = 30


@dataclass(frozen=True)
class RollupStats:
    hours: int
    monitors: int


# `date_trunc('hour', …)` is the grouping key, and the INSERT covers exactly one
# closed hour: rolling up the *current* hour would write a partial row that the
# next run would have to correct.
#
# ON CONFLICT DO UPDATE makes the job idempotent — re-running it for an hour
# that was already rolled up recomputes rather than failing or double-counting,
# which matters because a retry after a crash is normal operation.
_ROLLUP_SQL = text("""
INSERT INTO rollups_hourly (monitor_id, hour, checks, failures, p95_ms)
SELECT
    monitor_id,
    date_trunc('hour', checked_at)  AS hour,
    count(*)                        AS checks,
    count(*) FILTER (WHERE NOT ok)  AS failures,
    COALESCE(
        percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
            FILTER (WHERE latency_ms IS NOT NULL),
        0
    )::int                          AS p95_ms
FROM check_results
WHERE checked_at >= :start
  AND checked_at <  :end
GROUP BY monitor_id, date_trunc('hour', checked_at)
ON CONFLICT (monitor_id, hour) DO UPDATE
SET checks   = EXCLUDED.checks,
    failures = EXCLUDED.failures,
    p95_ms   = EXCLUDED.p95_ms
""")


async def rollup_hour(db: AsyncSession, *, hour_start: datetime) -> int:
    """Aggregate one closed hour. Returns the number of rows written."""
    # `rowcount` is only defined on a CursorResult, which is what a DML
    # statement returns; the cast tells the type checker that.
    result = cast(
        CursorResult[Any],
        await db.execute(
            _ROLLUP_SQL, {"start": hour_start, "end": hour_start + timedelta(hours=1)}
        ),
    )
    await db.commit()
    return result.rowcount or 0


def previous_hour(now: datetime) -> datetime:
    """The most recent *complete* hour boundary."""
    return now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


async def prune_raw_checks(
    db: AsyncSession, *, older_than_days: int = RAW_RETENTION_DAYS, batch_size: int = 10_000
) -> int:
    """Delete raw check rows older than the retention window.

    Deletes in batches rather than one statement: a single DELETE over millions
    of rows holds locks and bloats WAL for as long as it runs. Only rows that
    have already been rolled up are eligible, so pruning can never destroy
    history that was not summarised first.
    """
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    total = 0

    while True:
        result = cast(
            CursorResult[Any],
            await db.execute(
                text("""
                DELETE FROM check_results
                WHERE id IN (
                    SELECT c.id
                    FROM check_results c
                    WHERE c.checked_at < :cutoff
                      AND EXISTS (
                          SELECT 1 FROM rollups_hourly r
                          WHERE r.monitor_id = c.monitor_id
                            AND r.hour = date_trunc('hour', c.checked_at)
                      )
                    LIMIT :batch
                )
            """),
                {"cutoff": cutoff, "batch": batch_size},
            ),
        )
        await db.commit()
        deleted = result.rowcount or 0
        total += deleted
        if deleted < batch_size:
            break

    if total:
        logger.info("pruned raw check results", extra={"deleted": total, "cutoff": str(cutoff)})
    return total


# Reading uptime from rollups instead of raw rows. Falls back to the raw table
# only for the portion of the window the rollups do not cover yet (the current,
# still-open hour).
_ROLLUP_UPTIME_SQL = text("""
WITH rolled AS (
    SELECT
        COALESCE(sum(checks), 0)   AS checks,
        COALESCE(sum(failures), 0) AS failures,
        COALESCE(max(p95_ms), 0)   AS p95_ms
    FROM rollups_hourly
    WHERE monitor_id = :monitor_id
      -- Cast explicitly: asyncpg sends bind parameters untyped, and
      -- date_trunc is overloaded, so Postgres cannot pick an overload.
      AND hour >= date_trunc('hour', CAST(:since AS timestamptz))
      AND hour <  date_trunc('hour', now())
),
live AS (
    SELECT
        count(*)                       AS checks,
        count(*) FILTER (WHERE NOT ok) AS failures,
        COALESCE(
            percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                FILTER (WHERE latency_ms IS NOT NULL),
            0
        )::int AS p95_ms
    FROM check_results
    WHERE monitor_id = :monitor_id
      AND checked_at >= date_trunc('hour', now())
)
SELECT
    rolled.checks + live.checks     AS checks,
    rolled.failures + live.failures AS failures,
    -- Counts recombine exactly; percentiles do not. The true p95 over a window
    -- cannot be recovered from per-hour p95s, so this reports the worst hour's
    -- p95 — a deliberately conservative over-estimate rather than a figure that
    -- looks exact and is quietly wrong. Query the raw table for a true p95
    -- within the retention window.
    greatest(rolled.p95_ms, live.p95_ms) AS p95_ms
FROM rolled, live
""")


@dataclass(frozen=True)
class UptimeFromRollups:
    checks: int
    failures: int
    p95_ms: int
    source: str = "rollups"

    @property
    def uptime_pct(self) -> float:
        if self.checks == 0:
            return 0.0
        return round(100.0 * (self.checks - self.failures) / self.checks, 3)


async def uptime_from_rollups(
    db: AsyncSession, monitor_id: object, *, since: datetime
) -> UptimeFromRollups:
    row = (await db.execute(_ROLLUP_UPTIME_SQL, {"monitor_id": monitor_id, "since": since})).one()
    return UptimeFromRollups(
        checks=int(row.checks or 0),
        failures=int(row.failures or 0),
        p95_ms=int(row.p95_ms or 0),
    )
