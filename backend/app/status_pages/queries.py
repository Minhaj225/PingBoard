"""Uptime aggregation.

These run in the database rather than pulling raw `check_results` into Python:
a 90-day window on a 30-second monitor is a quarter of a million rows, and
counting them in the application would mean shipping all of it over the wire to
produce 90 numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_UPTIME_DAYS = 90


@dataclass(frozen=True)
class DailyUptime:
    day: date
    checks: int
    failures: int

    @property
    def uptime_pct(self) -> float:
        if self.checks == 0:
            return 0.0
        return round(100.0 * (self.checks - self.failures) / self.checks, 2)

    @property
    def state(self) -> str:
        """A day's colour band: no data, clean, degraded, or bad."""
        if self.checks == 0:
            return "no_data"
        if self.failures == 0:
            return "up"
        return "degraded" if self.uptime_pct >= 95 else "down"


# `generate_series` produces the full window first, then check_results is joined
# onto it. Without that, days with no checks at all would simply be missing from
# the result and the bar chart would silently compress — a gap has to render as
# a gap, not vanish.
_DAILY_UPTIME_SQL = text("""
WITH days AS (
    SELECT generate_series(
        date_trunc('day', now() AT TIME ZONE 'UTC') - make_interval(days => :days - 1),
        date_trunc('day', now() AT TIME ZONE 'UTC'),
        interval '1 day'
    )::date AS day
),
daily AS (
    SELECT
        (checked_at AT TIME ZONE 'UTC')::date AS day,
        count(*)                              AS checks,
        count(*) FILTER (WHERE NOT ok)        AS failures
    FROM check_results
    WHERE monitor_id = :monitor_id
      AND checked_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                        - make_interval(days => :days - 1)
    GROUP BY 1
)
SELECT
    days.day,
    COALESCE(daily.checks, 0)   AS checks,
    COALESCE(daily.failures, 0) AS failures
FROM days
LEFT JOIN daily USING (day)
ORDER BY days.day
""")


async def daily_uptime(
    db: AsyncSession, monitor_id: UUID, *, days: int = DEFAULT_UPTIME_DAYS
) -> list[DailyUptime]:
    rows = (await db.execute(_DAILY_UPTIME_SQL, {"monitor_id": monitor_id, "days": days})).all()
    return [DailyUptime(day=row.day, checks=row.checks, failures=row.failures) for row in rows]


_WINDOW_UPTIME_SQL = text("""
SELECT
    count(*)                       AS checks,
    count(*) FILTER (WHERE NOT ok) AS failures,
    -- percentile_cont needs a sorted set; NULL latencies (timeouts) are
    -- excluded so they don't skew the percentile toward zero.
    COALESCE(
        percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
            FILTER (WHERE latency_ms IS NOT NULL),
        0
    ) AS p95_ms
FROM check_results
WHERE monitor_id = :monitor_id
  AND checked_at >= :since
""")


@dataclass(frozen=True)
class WindowUptime:
    checks: int
    failures: int
    p95_ms: int

    @property
    def uptime_pct(self) -> float:
        if self.checks == 0:
            return 0.0
        return round(100.0 * (self.checks - self.failures) / self.checks, 3)


async def window_uptime(db: AsyncSession, monitor_id: UUID, *, since: datetime) -> WindowUptime:
    row = (await db.execute(_WINDOW_UPTIME_SQL, {"monitor_id": monitor_id, "since": since})).one()
    return WindowUptime(checks=row.checks, failures=row.failures, p95_ms=int(row.p95_ms or 0))


WINDOWS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}
