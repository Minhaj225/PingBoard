"""Notification channel model."""

from __future__ import annotations

import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin


class ChannelType(enum.StrEnum):
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"


channel_type_enum = Enum(
    ChannelType,
    name="channel_type",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class NotificationChannel(UUIDMixin, TimestampMixin, Base):
    """Where an organization wants to be told about incidents.

    `config` holds the type-specific payload — a webhook URL for Slack/Discord,
    a recipient address for email. It is **secret**: a webhook URL is a bearer
    credential for posting into someone's workspace, so it is masked on read
    (see `app.channels.schemas.mask_config`).
    """

    __tablename__ = "notification_channels"

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[ChannelType] = mapped_column(channel_type_enum, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
