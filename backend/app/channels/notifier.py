"""Notification delivery.

One `Notifier` protocol, one small implementation per channel type. Keeping
them separate means Slack's payload quirks never leak into the email path, and
adding a new destination is a new class plus a registry entry.

Nothing here is called inline from the checker's hot path — Phase 4 enqueues a
job and the worker delivers. A webhook that hangs for 30 seconds must never slow
down monitoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.channels.models import ChannelType
from app.core.mail import send_email

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_S = 10.0


class NotificationError(Exception):
    """Delivery failed. Retriable unless stated otherwise."""


@dataclass(frozen=True)
class Notification:
    """A channel-agnostic message. Each notifier renders it for its medium."""

    title: str
    body: str
    monitor_name: str
    monitor_url: str
    # "down" | "up" | "update" — drives colour and wording per channel.
    kind: str

    @property
    def is_bad_news(self) -> bool:
        return self.kind == "down"


class Notifier(Protocol):
    async def send(
        self, config: dict[str, Any], notification: Notification, client: httpx.AsyncClient
    ) -> None: ...


class SlackNotifier:
    """Posts to a Slack incoming webhook."""

    async def send(
        self, config: dict[str, Any], notification: Notification, client: httpx.AsyncClient
    ) -> None:
        url = _require(config, "webhook_url")
        colour = {"down": "#d03b3b", "up": "#0ca30c"}.get(notification.kind, "#64748b")

        payload = {
            "text": notification.title,
            "attachments": [
                {
                    "color": colour,
                    "title": notification.monitor_name,
                    "title_link": notification.monitor_url,
                    "text": notification.body,
                    "footer": "PingBoard",
                }
            ],
        }
        await _post_webhook(client, url, payload)


class DiscordNotifier:
    """Posts to a Discord webhook. Same idea as Slack, different envelope."""

    async def send(
        self, config: dict[str, Any], notification: Notification, client: httpx.AsyncClient
    ) -> None:
        url = _require(config, "webhook_url")
        colour = {"down": 0xD03B3B, "up": 0x0CA30C}.get(notification.kind, 0x64748B)

        payload = {
            "username": "PingBoard",
            "embeds": [
                {
                    "title": f"{notification.title} — {notification.monitor_name}",
                    "url": notification.monitor_url,
                    "description": notification.body,
                    "color": colour,
                }
            ],
        }
        await _post_webhook(client, url, payload)


class EmailNotifier:
    async def send(
        self, config: dict[str, Any], notification: Notification, client: httpx.AsyncClient
    ) -> None:
        recipient = _require(config, "to")
        body = (
            f"{notification.body}\n\n"
            f"Monitor: {notification.monitor_name}\n"
            f"URL: {notification.monitor_url}\n"
        )
        try:
            await send_email(to=recipient, subject=notification.title, body=body)
        except Exception as exc:
            raise NotificationError(f"SMTP delivery failed: {exc}") from exc


_REGISTRY: dict[ChannelType, Notifier] = {
    ChannelType.SLACK: SlackNotifier(),
    ChannelType.DISCORD: DiscordNotifier(),
    ChannelType.EMAIL: EmailNotifier(),
}


def get_notifier(channel_type: ChannelType) -> Notifier:
    notifier = _REGISTRY.get(channel_type)
    if notifier is None:
        raise NotificationError(f"No notifier registered for {channel_type}")
    return notifier


def _require(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise NotificationError(f"Channel config is missing {key!r}")
    return value


async def _post_webhook(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> None:
    try:
        response = await client.post(url, json=payload, timeout=WEBHOOK_TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise NotificationError(f"Webhook request failed: {exc}") from exc

    if response.status_code >= 400:
        # 4xx means the webhook is wrong (revoked, malformed) and retrying will
        # not help; 5xx is worth another attempt. The caller decides, so the
        # status is carried in the message.
        raise NotificationError(f"Webhook returned {response.status_code}: {response.text[:200]}")
