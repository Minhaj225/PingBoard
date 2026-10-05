"""The notification delivery job.

Separated from the checker so a slow or wedged webhook can never hold up
monitoring. The checker enqueues; this runs on its own, with retries.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.channels.models import NotificationChannel
from app.channels.notifier import Notification, NotificationError, get_notifier
from app.core.db import SessionLocal

logger = logging.getLogger(__name__)

# Webhook endpoints fail transiently often enough that one attempt is not
# enough; ARQ spaces retries out via `retry_jobs`/backoff.
MAX_NOTIFY_ATTEMPTS = 3


async def deliver_notification(
    ctx: dict[str, Any],
    org_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fan a notification out to every active channel in the organization."""
    client: httpx.AsyncClient = ctx["http_client"]
    notification = Notification(**payload)

    async with SessionLocal() as db:
        channels = list(
            await db.scalars(
                select(NotificationChannel).where(
                    NotificationChannel.org_id == UUID(org_id),
                    NotificationChannel.is_active.is_(True),
                )
            )
        )

    if not channels:
        return {"delivered": 0, "channels": 0}

    delivered = 0
    failures: list[str] = []

    for channel in channels:
        try:
            notifier = get_notifier(channel.type)
            await notifier.send(channel.config, notification, client)
            delivered += 1
        except NotificationError as exc:
            # One broken channel must not stop the others from being told.
            failures.append(f"{channel.name}: {exc}")
            logger.warning(
                "notification delivery failed",
                extra={"channel_id": str(channel.id), "channel_type": channel.type.value},
            )

    if failures and delivered == 0:
        # Nothing got through — let ARQ retry the whole fan-out.
        raise NotificationError("; ".join(failures))

    return {"delivered": delivered, "channels": len(channels), "failures": failures}


def incident_opened(monitor_name: str, monitor_url: str, cause: str | None) -> dict[str, Any]:
    return {
        "title": "🔴 Incident opened",
        "body": cause or "The check failed.",
        "monitor_name": monitor_name,
        "monitor_url": monitor_url,
        "kind": "down",
    }


def incident_resolved(monitor_name: str, monitor_url: str, message: str) -> dict[str, Any]:
    return {
        "title": "🟢 Incident resolved",
        "body": message,
        "monitor_name": monitor_name,
        "monitor_url": monitor_url,
        "kind": "up",
    }


def incident_update(monitor_name: str, monitor_url: str, message: str) -> dict[str, Any]:
    return {
        "title": "📝 Incident update",
        "body": message,
        "monitor_name": monitor_name,
        "monitor_url": monitor_url,
        "kind": "update",
    }
