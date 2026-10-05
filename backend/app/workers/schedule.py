"""Pure scheduling arithmetic.

Kept free of I/O on purpose. Schedulers go wrong in small, quiet ways — drift,
double-enqueues, a paused monitor that never resumes — and those are far easier
to pin down against a fake clock than against a running loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# How many consecutive failures before a monitor is declared down. One failed
# check is usually a blip; this is the flap protection the plan calls for.
DEFAULT_FAILURE_THRESHOLD = 3


def next_run_after(*, previous_run_at: datetime, interval_s: int, now: datetime) -> datetime:
    """Advance a schedule to the next slot strictly after `now`.

    Naively doing `previous + interval` drifts and, worse, leaves a monitor
    permanently behind if the worker was down: a monitor on a 30s interval that
    missed an hour would otherwise be due 120 times in a row and stampede the
    queue on restart. Catching up to the next future slot keeps the cadence
    aligned to the original offset while firing exactly once.
    """
    interval = timedelta(seconds=max(1, interval_s))

    if previous_run_at > now:
        return previous_run_at

    missed = (now - previous_run_at) // interval
    candidate = previous_run_at + (missed + 1) * interval

    # Guard against an interval change making the arithmetic land on `now`.
    return candidate if candidate > now else candidate + interval


@dataclass(frozen=True)
class StatusTransition:
    """The result of folding one check outcome into a monitor's status."""

    status: str
    consecutive_failures: int
    went_down: bool
    recovered: bool


def apply_check_outcome(
    *,
    current_status: str,
    consecutive_failures: int,
    ok: bool,
    threshold: int = DEFAULT_FAILURE_THRESHOLD,
) -> StatusTransition:
    """Fold a check result into the monitor's status.

    A success resets the counter and restores `up` immediately — recovery is
    never delayed. A failure increments, and only at `threshold` does the
    monitor flip to `down`. `went_down` / `recovered` fire on the *edge* only,
    which is exactly what Phase 4 needs to open and close incidents without
    re-notifying on every subsequent check.
    """
    if ok:
        return StatusTransition(
            status="up",
            consecutive_failures=0,
            went_down=False,
            recovered=current_status == "down",
        )

    failures = consecutive_failures + 1
    crossed = failures >= max(1, threshold)

    return StatusTransition(
        status="down" if crossed else current_status,
        consecutive_failures=failures,
        went_down=crossed and current_status != "down",
        recovered=False,
    )
