from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.monitors.rollups import UptimeFromRollups, previous_hour


class TestPreviousHour:
    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            (datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC), datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
            (datetime(2026, 1, 1, 13, 59, 59, tzinfo=UTC), datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
            (datetime(2026, 1, 1, 13, 5, 0, tzinfo=UTC), datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        ],
    )
    def test_returns_the_last_closed_hour(self, now: datetime, expected: datetime) -> None:
        assert previous_hour(now) == expected

    def test_never_returns_the_current_hour(self) -> None:
        """Rolling up the open hour would write a partial row."""
        now = datetime(2026, 1, 1, 13, 30, tzinfo=UTC)
        assert previous_hour(now) < now.replace(minute=0, second=0, microsecond=0)

    def test_crosses_midnight(self) -> None:
        assert previous_hour(datetime(2026, 1, 2, 0, 10, tzinfo=UTC)) == datetime(
            2026, 1, 1, 23, 0, tzinfo=UTC
        )

    def test_is_exactly_one_hour_back(self) -> None:
        now = datetime(2026, 6, 15, 7, 42, 13, tzinfo=UTC)
        assert now.replace(minute=0, second=0, microsecond=0) - previous_hour(now) == timedelta(
            hours=1
        )


class TestUptimeFromRollups:
    def test_percentage(self) -> None:
        assert UptimeFromRollups(checks=1000, failures=20, p95_ms=90).uptime_pct == 98.0

    def test_no_data_is_zero_not_a_crash(self) -> None:
        assert UptimeFromRollups(checks=0, failures=0, p95_ms=0).uptime_pct == 0.0

    def test_perfect(self) -> None:
        assert UptimeFromRollups(checks=50_000, failures=0, p95_ms=5).uptime_pct == 100.0

    def test_total_outage(self) -> None:
        assert UptimeFromRollups(checks=10, failures=10, p95_ms=0).uptime_pct == 0.0

    def test_source_is_labelled(self) -> None:
        """Callers can tell an aggregated figure from a raw one."""
        assert UptimeFromRollups(checks=1, failures=0, p95_ms=1).source == "rollups"
