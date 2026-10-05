"""Request and response bodies for notification channels."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.channels.models import ChannelType
from app.core.config import get_settings

# Keys whose values are credentials and must never be returned in full.
SECRET_KEYS = frozenset({"webhook_url"})


def mask_config(config: dict[str, Any]) -> dict[str, Any]:
    """Blank out credential values for read responses.

    A Slack/Discord webhook URL is a bearer token: anyone holding it can post
    into that workspace. Showing enough to recognise which hook is configured,
    and no more, is the point.
    """
    masked: dict[str, Any] = {}
    for key, value in config.items():
        if key in SECRET_KEYS and isinstance(value, str):
            masked[key] = _mask(value)
        else:
            masked[key] = value
    return masked


def _mask(value: str) -> str:
    # Keep the host so the user can tell Slack from Discord, drop the secret path.
    prefix = value.split("://", 1)
    host = prefix[1].split("/", 1)[0] if len(prefix) == 2 else value[:12]
    return f"{prefix[0]}://{host}/…" if len(prefix) == 2 else f"{host}…"


def _validate_webhook_url(url: str) -> str:
    """Require HTTPS in production.

    Real Slack and Discord webhooks are always HTTPS, and the URL is a bearer
    credential — sending it in clear text would leak it. Plain HTTP is allowed
    outside production only so a local receiver can be used while developing.
    """
    if url.startswith("https://"):
        return url
    if url.startswith("http://") and not get_settings().is_prod:
        return url
    raise ValueError("Webhook URL must start with https://")


class SlackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webhook_url: Annotated[str, AfterValidator(_validate_webhook_url)] = Field(
        min_length=1, max_length=2048
    )


class DiscordConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webhook_url: Annotated[str, AfterValidator(_validate_webhook_url)] = Field(
        min_length=1, max_length=2048
    )


class EmailConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: EmailStr


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: ChannelType
    config: dict[str, Any]

    @model_validator(mode="after")
    def _validate_config(self) -> ChannelCreate:
        """Validate `config` against the shape its `type` requires."""
        validators: dict[ChannelType, type[BaseModel]] = {
            ChannelType.SLACK: SlackConfig,
            ChannelType.DISCORD: DiscordConfig,
            ChannelType.EMAIL: EmailConfig,
        }
        validators[self.type].model_validate(self.config)
        return self


class ChannelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class ChannelRead(BaseModel):
    """Read shape — `config` is always masked on the way out."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    type: ChannelType
    config: dict[str, Any]
    is_active: bool
    created_at: datetime


class ChannelTestResult(BaseModel):
    delivered: Literal[True, False]
    detail: str | None = None
