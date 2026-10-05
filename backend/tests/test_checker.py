from __future__ import annotations

import dataclasses

import httpx
import pytest

from app.monitors.checker import CheckOutcome, evaluate_assertions, run_check
from app.monitors.schemas import Assertions


class FakeMonitor:
    def __init__(
        self,
        *,
        url: str = "https://example.com",
        method: str = "GET",
        timeout_ms: int = 5000,
        assertions: Assertions | None = None,
    ) -> None:
        self.url = url
        self.method = method
        self.timeout_ms = timeout_ms
        self.assertions = assertions or Assertions()


def client_returning(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestEvaluateAssertions:
    def test_empty_assertions_accept_2xx(self) -> None:
        assert evaluate_assertions(Assertions(), status_code=200, latency_ms=10, body="") is None

    @pytest.mark.parametrize("status", [200, 201, 204, 301, 302, 399])
    def test_empty_assertions_accept_2xx_and_3xx(self, status: int) -> None:
        assert evaluate_assertions(Assertions(), status_code=status, latency_ms=1, body="") is None

    @pytest.mark.parametrize("status", [400, 401, 404, 500, 503])
    def test_empty_assertions_reject_4xx_5xx(self, status: int) -> None:
        failure = evaluate_assertions(Assertions(), status_code=status, latency_ms=1, body="")
        assert failure is not None
        assert str(status) in failure

    def test_explicit_status_overrides_the_default(self) -> None:
        """A monitor may legitimately expect a 404 or a 401."""
        expect_404 = Assertions(status_code=404)
        assert evaluate_assertions(expect_404, status_code=404, latency_ms=1, body="") is None
        assert evaluate_assertions(expect_404, status_code=200, latency_ms=1, body="") is not None

    def test_latency_threshold(self) -> None:
        assertions = Assertions(max_latency_ms=100)
        assert evaluate_assertions(assertions, status_code=200, latency_ms=100, body="") is None
        failure = evaluate_assertions(assertions, status_code=200, latency_ms=101, body="")
        assert failure is not None and "101ms" in failure

    def test_body_contains(self) -> None:
        a = Assertions(body_contains="healthy")
        assert evaluate_assertions(a, status_code=200, latency_ms=1, body='{"s":"healthy"}') is None
        assert evaluate_assertions(a, status_code=200, latency_ms=1, body="nope") is not None

    def test_body_not_contains(self) -> None:
        a = Assertions(body_not_contains="Traceback")
        assert evaluate_assertions(a, status_code=200, latency_ms=1, body="fine") is None
        assert evaluate_assertions(a, status_code=200, latency_ms=1, body="Traceback!") is not None

    def test_first_failure_wins(self) -> None:
        """Status is checked before body, so the message names the real cause."""
        assertions = Assertions(status_code=200, body_contains="ok")
        failure = evaluate_assertions(assertions, status_code=500, latency_ms=1, body="")
        assert failure is not None and "500" in failure

    def test_all_assertions_together(self) -> None:
        assertions = Assertions(
            status_code=200, max_latency_ms=1000, body_contains="ok", body_not_contains="error"
        )
        assert evaluate_assertions(assertions, status_code=200, latency_ms=50, body="ok") is None


class TestRunCheck:
    async def test_successful_probe(self) -> None:
        async with client_returning(lambda r: httpx.Response(200, text="ok")) as client:
            outcome = await run_check(FakeMonitor(), client)
        assert outcome.ok
        assert outcome.status_code == 200
        assert outcome.error is None
        assert outcome.latency_ms is not None and outcome.latency_ms >= 0

    async def test_failing_status_is_reported_not_raised(self) -> None:
        async with client_returning(lambda r: httpx.Response(503)) as client:
            outcome = await run_check(FakeMonitor(), client)
        assert not outcome.ok
        assert outcome.status_code == 503
        assert outcome.error

    async def test_timeout_is_captured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        async with client_returning(handler) as client:
            outcome = await run_check(FakeMonitor(timeout_ms=250), client)
        assert not outcome.ok
        assert outcome.status_code is None
        assert outcome.error is not None and "250ms" in outcome.error

    async def test_connection_error_is_captured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        async with client_returning(handler) as client:
            outcome = await run_check(FakeMonitor(), client)
        assert not outcome.ok
        assert outcome.error is not None and "refused" in outcome.error

    async def test_method_is_passed_through(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.method)
            return httpx.Response(200)

        async with client_returning(handler) as client:
            await run_check(FakeMonitor(method="head"), client)
        assert seen == ["HEAD"]

    async def test_assertions_accepted_as_a_plain_dict(self) -> None:
        """The ORM stores JSONB, so a dict must work as well as the model."""
        monitor = FakeMonitor()
        monitor.assertions = {"status_code": 418}  # type: ignore[assignment]
        async with client_returning(lambda r: httpx.Response(418)) as client:
            outcome = await run_check(monitor, client)
        assert outcome.ok

    async def test_body_assertion_against_real_payload(self) -> None:
        monitor = FakeMonitor(assertions=Assertions(body_contains='"status":"ok"'))
        body = '{"status":"ok"}'
        async with client_returning(lambda r: httpx.Response(200, text=body)) as client:
            outcome = await run_check(monitor, client)
        assert outcome.ok

    async def test_outcome_is_immutable(self) -> None:
        """Frozen so a caller cannot rewrite a result after it is produced."""
        outcome = CheckOutcome(ok=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.ok = False  # type: ignore[misc]
