"""Notification channel endpoints."""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.auth.deps import DbSession
from app.channels.models import NotificationChannel
from app.channels.notifier import Notification, NotificationError, get_notifier
from app.channels.schemas import (
    ChannelCreate,
    ChannelRead,
    ChannelTestResult,
    ChannelUpdate,
    mask_config,
)
from app.orgs.scope import OrgAdmin, OrgViewer

router = APIRouter(prefix="/channels", tags=["channels"])


def _to_read(channel: NotificationChannel) -> ChannelRead:
    """Always mask on the way out — a webhook URL is a credential."""
    read = ChannelRead.model_validate(channel)
    return read.model_copy(update={"config": mask_config(channel.config)})


async def _get_for_org(db: DbSession, channel_id: UUID, org_id: UUID) -> NotificationChannel:
    channel = await db.scalar(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id, NotificationChannel.org_id == org_id
        )
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel


@router.get("", response_model=list[ChannelRead], summary="List notification channels")
async def list_channels(db: DbSession, membership: OrgViewer) -> list[ChannelRead]:
    channels = await db.scalars(
        select(NotificationChannel)
        .where(NotificationChannel.org_id == membership.org_id)
        .order_by(NotificationChannel.created_at)
    )
    return [_to_read(channel) for channel in channels]


@router.post(
    "",
    response_model=ChannelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a notification channel",
)
async def create_channel(
    payload: ChannelCreate, db: DbSession, membership: OrgAdmin
) -> ChannelRead:
    channel = NotificationChannel(
        org_id=membership.org_id,
        name=payload.name,
        type=payload.type,
        config=payload.config,
        is_active=True,
    )
    db.add(channel)
    await db.commit()
    return _to_read(channel)


@router.patch("/{channel_id}", response_model=ChannelRead, summary="Update a channel")
async def update_channel(
    channel_id: UUID, payload: ChannelUpdate, db: DbSession, membership: OrgAdmin
) -> ChannelRead:
    channel = await _get_for_org(db, channel_id, membership.org_id)

    changes = payload.model_dump(exclude_unset=True)
    if "config" in changes and changes["config"] is not None:
        # Re-validate the replacement against the channel's own type.
        ChannelCreate(name=channel.name, type=channel.type, config=changes["config"])

    for field, value in changes.items():
        setattr(channel, field, value)

    await db.commit()
    return _to_read(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a channel")
async def delete_channel(channel_id: UUID, db: DbSession, membership: OrgAdmin) -> Response:
    channel = await _get_for_org(db, channel_id, membership.org_id)
    await db.delete(channel)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{channel_id}/test",
    response_model=ChannelTestResult,
    summary="Send a test notification",
)
async def test_channel(channel_id: UUID, db: DbSession, membership: OrgAdmin) -> ChannelTestResult:
    """Deliver synchronously so the user gets immediate feedback.

    This is the one place a notification is *not* queued: someone configuring a
    webhook needs to know right now whether it works, and a background job that
    silently fails would be useless feedback.
    """
    channel = await _get_for_org(db, channel_id, membership.org_id)

    notification = Notification(
        title="✅ PingBoard test notification",
        body=f"If you can read this, “{channel.name}” is wired up correctly.",
        monitor_name="Test",
        monitor_url="https://pingboard.local",
        kind="update",
    )

    try:
        notifier = get_notifier(channel.type)
        async with httpx.AsyncClient() as client:
            await notifier.send(channel.config, notification, client)
    except NotificationError as exc:
        # A failed test is a successful request reporting bad config, not a 500.
        return ChannelTestResult(delivered=False, detail=str(exc))

    return ChannelTestResult(delivered=True)
