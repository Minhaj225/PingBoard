from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.workers.schedule import (
    DEFAULT_FAILURE_THRESHOLD,
    apply_check_outcome,
    next_run_after,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestNextRunAfter:
    def test_advances_by_exactly_one_interval_when_on_time(self) -> None:
        previous = NOW - timedelta(seconds=1)
        assert next_run_after(previous_run_at=previous, interval_s=60, now=NOW) == (
            previous + timedelta(seconds=60)
        )

    def test_result_is_always_in_the_future(self) -> None:
        for seconds_late in (0, 1, 59, 60, 61, 3600):
            previous = NOW - timedelta(seconds=seconds_late)
            assert next_run_after(previous_run_at=previous, interval_s=60, now=NOW) > NOW

    def test_due_exactly_now_moves_forward_not_sideways(self) -> None:
        """`previous == now` must not return `now` — that would re-fire forever."""
        assert next_run_after(previous_run_at=NOW, interval_s=30, now=NOW) == (
            NOW + timedelta(seconds=30)
        )

    def test_catches_up_in_one_hop_after_an_outage(self) -> None:
        """A worker down for an hour must not queue 120 backlogged runs."""
        previous = NOW - timedelta(hours=1)
        result = next_run_after(previous_run_at=previous, interval_s=30, now=NOW)
        assert NOW < result <= NOW + timedelta(seconds=30)

    def test_cadence_offset_is_preserved(self) -> None:
        """Catching up keeps the original phase, so checks stay evenly spaced."""
        previous = NOW - timedelta(seconds=185)  # 3 intervals + 5s, on a 60s cadence
        result = next_run_after(previous_run_at=previous, interval_s=60, now=NOW)
        assert (result - previous).total_seconds() % 60 == 0

    def test_future_schedule_is_left_alone(self) -> None:
        """A monitor not yet due must not be pulled forward."""
        future = NOW + timedelta(seconds=45)
        assert next_run_after(previous_run_at=future, interval_s=60, now=NOW) == future

    @pytest.mark.parametrize("interval", [0, -1, -600])
    def test_non_positive_interval_still_advances(self, interval: int) -> None:
        """A bad interval must not produce an infinite-rate schedule."""
        assert next_run_after(previous_run_at=NOW, interval_s=interval, now=NOW) > NOW

    def test_is_deterministic(self) -> None:
        args = {"previous_run_at": NOW - timedelta(seconds=90), "interval_s": 60, "now": NOW}
        assert next_run_after(**args) == next_run_after(**args)


class TestApplyCheckOutcome:
    def test_first_failure_does_not_flip_status(self) -> None:
        result = apply_check_outcome(current_status="up", consecutive_failures=0, ok=False)
        assert result.status == "up"
        assert result.consecutive_failures == 1
        assert not result.went_down

    def test_flips_down_exactly_at_the_threshold(self) -> None:
        status, failures = "up", 0
        transitions = []
        for _ in range(DEFAULT_FAILURE_THRESHOLD):
            result = apply_check_outcome(
                current_status=status, consecutive_failures=failures, ok=False
            )
            status, failures = result.status, result.consecutive_failures
            transitions.append(result.went_down)

        assert transitions == [False] * (DEFAULT_FAILURE_THRESHOLD - 1) + [True]
        assert status == "down"

    def test_went_down_fires_once_not_on_every_later_failure(self) -> None:
        """Phase 4 opens an incident on this edge; it must not repeat."""
        result = apply_check_outcome(current_status="down", consecutive_failures=9, ok=False)
        assert result.status == "down"
        assert not result.went_down

    def test_success_resets_the_counter(self) -> None:
        result = apply_check_outcome(current_status="up", consecutive_failures=2, ok=True)
        assert result.consecutive_failures == 0
        assert result.status == "up"

    def test_recovery_is_immediate_and_edge_triggered(self) -> None:
        result = apply_check_outcome(current_status="down", consecutive_failures=7, ok=True)
        assert result.status == "up"
        assert result.recovered
        assert result.consecutive_failures == 0

    def test_success_while_already_up_is_not_a_recovery(self) -> None:
        result = apply_check_outcome(current_status="up", consecutive_failures=0, ok=True)
        assert not result.recovered

    def test_first_ever_check_leaves_unknown_behind(self) -> None:
        assert (
            apply_check_outcome(current_status="unknown", consecutive_failures=0, ok=True).status
            == "up"
        )

    def test_unknown_to_down_still_reports_the_edge(self) -> None:
        """A monitor that has never succeeded must still open an incident."""
        result = apply_check_outcome(current_status="unknown", consecutive_failures=2, ok=False)
        assert result.status == "down"
        assert result.went_down

    @pytest.mark.parametrize("threshold", [1, 2, 5])
    def test_threshold_is_configurable(self, threshold: int) -> None:
        status, failures = "up", 0
        for attempt in range(1, threshold + 1):
            result = apply_check_outcome(
                current_status=status,
                consecutive_failures=failures,
                ok=False,
                threshold=threshold,
            )
            status, failures = result.status, result.consecutive_failures
            assert result.went_down is (attempt == threshold)

    def test_zero_threshold_is_clamped_to_one(self) -> None:
        result = apply_check_outcome(
            current_status="up", consecutive_failures=0, ok=False, threshold=0
        )
        assert result.went_down
