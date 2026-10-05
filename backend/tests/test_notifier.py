from __future__ import annotations

import httpx
import pytest

from app.channels.models import ChannelType
from app.channels.notifier import (
    DiscordNotifier,
    Notification,
    NotificationError,
    SlackNotifier,
    get_notifier,
)
from app.channels.schemas import ChannelCreate, mask_config

DOWN = Notification(
    title="🔴 Incident opened",
    body="Expected status 200, got 503",
    monitor_name="Payments API",
    monitor_url="https://pay.example.com/health",
    kind="down",
)
UP = Notification(
    title="🟢 Incident resolved",
    body="Back to normal",
    monitor_name="Payments API",
    monitor_url="https://pay.example.com/health",
    kind="up",
)


def capture() -> tuple[list[httpx.Request], httpx.AsyncClient]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    return seen, httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestRegistry:
    @pytest.mark.parametrize("channel_type", list(ChannelType))
    def test_every_channel_type_has_a_notifier(self, channel_type: ChannelType) -> None:
        assert get_notifier(channel_type) is not None


class TestSlackNotifier:
    async def test_posts_to_the_configured_webhook(self) -> None:
        seen, client = capture()
        async with client:
            await SlackNotifier().send(
                {"webhook_url": "https://hooks.slack.test/abc"}, DOWN, client
            )
        assert len(seen) == 1
        assert str(seen[0].url) == "https://hooks.slack.test/abc"

    async def test_down_and_up_use_different_colours(self) -> None:
        import json

        seen, client = capture()
        async with client:
            await SlackNotifier().send({"webhook_url": "https://x.test/h"}, DOWN, client)
            await SlackNotifier().send({"webhook_url": "https://x.test/h"}, UP, client)

        colours = [json.loads(r.content)["attachments"][0]["color"] for r in seen]
        assert colours[0] != colours[1]

    async def test_missing_webhook_url_is_a_config_error(self) -> None:
        _, client = capture()
        async with client:
            with pytest.raises(NotificationError, match="webhook_url"):
                await SlackNotifier().send({}, DOWN, client)

    async def test_http_error_becomes_notification_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(NotificationError, match="Webhook request failed"):
                await SlackNotifier().send({"webhook_url": "https://x.test/h"}, DOWN, client)

    @pytest.mark.parametrize("status", [400, 403, 404, 500, 503])
    async def test_error_status_becomes_notification_error(self, status: int) -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, text="nope"))
        ) as client:
            with pytest.raises(NotificationError, match=str(status)):
                await SlackNotifier().send({"webhook_url": "https://x.test/h"}, DOWN, client)


class TestDiscordNotifier:
    async def test_sends_an_embed(self) -> None:
        import json

        seen, client = capture()
        async with client:
            await DiscordNotifier().send(
                {"webhook_url": "https://discord.test/api/webhooks/1/x"}, DOWN, client
            )
        body = json.loads(seen[0].content)
        assert body["embeds"][0]["title"].endswith("Payments API")
        assert body["embeds"][0]["url"] == DOWN.monitor_url


class TestConfigMasking:
    def test_webhook_url_secret_path_is_removed(self) -> None:
        masked = mask_config(
            {"webhook_url": "https://hooks.slack.com/services/T00/B00/SUPERSECRETTOKEN"}
        )
        assert "SUPERSECRETTOKEN" not in masked["webhook_url"]

    def test_host_is_kept_so_the_channel_is_recognisable(self) -> None:
        masked = mask_config({"webhook_url": "https://hooks.slack.com/services/T/B/C"})
        assert "hooks.slack.com" in masked["webhook_url"]

    def test_non_secret_keys_pass_through(self) -> None:
        assert mask_config({"to": "ops@example.com"}) == {"to": "ops@example.com"}

    def test_masking_is_idempotent(self) -> None:
        once = mask_config({"webhook_url": "https://hooks.slack.com/services/T/B/C"})
        assert mask_config(once) == once


class TestChannelConfigValidation:
    def test_slack_requires_a_webhook_url(self) -> None:
        with pytest.raises(ValueError):
            ChannelCreate(name="x", type=ChannelType.SLACK, config={})

    def test_email_requires_a_valid_address(self) -> None:
        with pytest.raises(ValueError):
            ChannelCreate(name="x", type=ChannelType.EMAIL, config={"to": "not-an-email"})

    def test_unknown_config_keys_are_rejected(self) -> None:
        """Stops a typo'd key from silently doing nothing at delivery time."""
        with pytest.raises(ValueError):
            ChannelCreate(
                name="x",
                type=ChannelType.SLACK,
                config={"webhook_url": "https://x.test/h", "webhok_url": "oops"},
            )

    def test_valid_config_is_accepted(self) -> None:
        channel = ChannelCreate(
            name="Ops", type=ChannelType.SLACK, config={"webhook_url": "https://x.test/h"}
        )
        assert channel.type is ChannelType.SLACK
