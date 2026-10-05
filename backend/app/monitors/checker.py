"""The HTTP probe itself.

`run_check` is a pure function of (monitor spec, http client): it performs one
request and reports what happened. It touches no database and no globals, so it
is trivially testable and reusable from both the API and the worker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.monitors.schemas import Assertions

# Bodies are only ever inspected for substrings; reading more than this from an
# unknown remote server is a memory risk for no benefit.
MAX_BODY_BYTES = 256 * 1024


class MonitorSpec(Protocol):
    """Only the fields a check actually needs — an ORM Monitor satisfies this."""

    url: str
    method: str
    timeout_ms: int

    @property
    def assertions(self) -> object: ...


@dataclass(frozen=True)
class CheckOutcome:
    ok: bool
    status_code: int | None = None
    latency_ms: int | None = None
    error: str | None = None


def evaluate_assertions(
    assertions: Assertions, *, status_code: int, latency_ms: int, body: str
) -> str | None:
    """Return the first failure message, or `None` when everything holds."""
    if assertions.status_code is not None:
        if status_code != assertions.status_code:
            return f"Expected status {assertions.status_code}, got {status_code}"
    elif not 200 <= status_code < 400:
        # Default expectation when no explicit status is configured.
        return f"Unexpected status {status_code}"

    if assertions.max_latency_ms is not None and latency_ms > assertions.max_latency_ms:
        return f"Response took {latency_ms}ms, over the {assertions.max_latency_ms}ms limit"

    if assertions.body_contains and assertions.body_contains not in body:
        return f"Body did not contain {assertions.body_contains!r}"

    if assertions.body_not_contains and assertions.body_not_contains in body:
        return f"Body contained {assertions.body_not_contains!r}"

    return None


async def run_check(monitor: MonitorSpec, client: httpx.AsyncClient) -> CheckOutcome:
    """Probe `monitor` once using the supplied client.

    The client is injected rather than created here so the caller controls
    connection pooling, and so tests can pass a mock transport.
    """
    assertions = (
        monitor.assertions
        if isinstance(monitor.assertions, Assertions)
        else Assertions.model_validate(monitor.assertions or {})
    )
    timeout = monitor.timeout_ms / 1000

    # A monotonic clock: wall-clock jumps (NTP, DST) must not corrupt latency.
    started = time.perf_counter()
    try:
        response = await client.request(
            monitor.method.upper(),
            monitor.url,
            timeout=timeout,
            follow_redirects=True,
        )
        body = _read_body(response)
    except httpx.TimeoutException:
        return CheckOutcome(
            ok=False,
            latency_ms=_elapsed_ms(started),
            error=f"Timed out after {monitor.timeout_ms}ms",
        )
    except httpx.TooManyRedirects:
        return CheckOutcome(ok=False, latency_ms=_elapsed_ms(started), error="Too many redirects")
    except httpx.HTTPError as exc:
        return CheckOutcome(
            ok=False,
            latency_ms=_elapsed_ms(started),
            error=_describe(exc),
        )

    latency_ms = _elapsed_ms(started)
    failure = evaluate_assertions(
        assertions,
        status_code=response.status_code,
        latency_ms=latency_ms,
        body=body,
    )
    return CheckOutcome(
        ok=failure is None,
        status_code=response.status_code,
        latency_ms=latency_ms,
        error=failure,
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _read_body(response: httpx.Response) -> str:
    raw = response.content[:MAX_BODY_BYTES]
    return raw.decode(response.encoding or "utf-8", errors="replace")


def _describe(exc: httpx.HTTPError) -> str:
    """A short, user-facing reason — never a raw traceback or internal path."""
    message = str(exc).strip() or exc.__class__.__name__
    return message[:500]
