from __future__ import annotations

from datetime import date

import pytest

from app.monitors.models import MonitorStatus
from app.status_pages.queries import DailyUptime, WindowUptime
from app.status_pages.schemas import PublicMonitor
from app.status_pages.service import DEGRADED_UPTIME_PCT, _overall, _public_status

DAY = date(2026, 1, 1)


class TestDailyUptime:
    def test_perfect_day(self) -> None:
        day = DailyUptime(day=DAY, checks=2880, failures=0)
        assert day.uptime_pct == 100.0
        assert day.state == "up"

    def test_total_outage(self) -> None:
        day = DailyUptime(day=DAY, checks=100, failures=100)
        assert day.uptime_pct == 0.0
        assert day.state == "down"

    def test_a_day_with_no_checks_is_not_a_zero_percent_day(self) -> None:
        """A gap must render as a gap, not as an outage."""
        day = DailyUptime(day=DAY, checks=0, failures=0)
        assert day.state == "no_data"

    @pytest.mark.parametrize(
        ("checks", "failures", "expected"),
        [
            (100, 1, "degraded"),  # 99%  — above the 95% band
            (100, 5, "degraded"),  # 95%  — exactly on the boundary
            (100, 6, "down"),  # 94%  — below it
            (100, 50, "down"),
        ],
    )
    def test_state_bands(self, checks: int, failures: int, expected: str) -> None:
        assert DailyUptime(day=DAY, checks=checks, failures=failures).state == expected

    def test_percentage_is_rounded_not_truncated(self) -> None:
        # 2 failures in 3 checks = 33.333…%
        assert DailyUptime(day=DAY, checks=3, failures=2).uptime_pct == 33.33

    def test_division_by_zero_is_impossible(self) -> None:
        assert DailyUptime(day=DAY, checks=0, failures=0).uptime_pct == 0.0


class TestWindowUptime:
    def test_uptime_percentage(self) -> None:
        assert WindowUptime(checks=1000, failures=1, p95_ms=120).uptime_pct == 99.9

    def test_empty_window(self) -> None:
        assert WindowUptime(checks=0, failures=0, p95_ms=0).uptime_pct == 0.0

    def test_three_decimals_so_three_nines_is_visible(self) -> None:
        """99.9% and 99.95% must not both round to 99.9."""
        assert WindowUptime(checks=10_000, failures=5, p95_ms=0).uptime_pct == 99.95


class TestPublicStatusMapping:
    def test_never_checked_is_unknown_not_operational(self) -> None:
        assert _public_status(MonitorStatus.UP, 0.0, total_checks=0) == "unknown"

    def test_unknown_status_stays_unknown(self) -> None:
        assert _public_status(MonitorStatus.UNKNOWN, 100.0, total_checks=10) == "unknown"

    def test_down_wins_over_a_good_history(self) -> None:
        """Currently down is currently down, whatever the 90-day average says."""
        assert _public_status(MonitorStatus.DOWN, 99.99, total_checks=10_000) == "down"

    def test_up_with_a_rough_history_reads_as_degraded(self) -> None:
        assert _public_status(MonitorStatus.UP, DEGRADED_UPTIME_PCT - 0.1, 1000) == "degraded"

    def test_up_with_a_clean_history_is_operational(self) -> None:
        assert _public_status(MonitorStatus.UP, 100.0, 1000) == "operational"


def monitor(status: str) -> PublicMonitor:
    return PublicMonitor(name="x", status=status, uptime_90d=100.0, days=[])  # type: ignore[arg-type]


class TestOverallBanner:
    def test_all_clear(self) -> None:
        assert _overall([monitor("operational"), monitor("operational")]) == "operational"

    def test_one_down_sets_the_banner_down(self) -> None:
        """The banner must never under-report — the worst state wins."""
        assert _overall([monitor("operational"), monitor("down")]) == "down"

    def test_down_outranks_degraded(self) -> None:
        assert _overall([monitor("degraded"), monitor("down")]) == "down"

    def test_degraded_outranks_unknown(self) -> None:
        assert _overall([monitor("unknown"), monitor("degraded")]) == "degraded"

    def test_empty_page_is_unknown_not_operational(self) -> None:
        """An empty page must not claim everything is fine."""
        assert _overall([]) == "unknown"
