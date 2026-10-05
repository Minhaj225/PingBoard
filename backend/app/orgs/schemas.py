"""Request and response bodies for the organization endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.orgs.models import MemberRole


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe identifier. Derived from the name when omitted.",
    )


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime


class OrgSummary(OrgRead):
    """An organization plus the caller's own role in it."""

    role: MemberRole


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    name: str | None
    role: MemberRole
    joined_at: datetime


class InviteCreate(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.VIEWER


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    email: str
    role: MemberRole
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InviteCreated(BaseModel):
    """The raw token is returned exactly once, at creation.

    Only its digest is stored, so this response (and the emailed link) is the
    single opportunity to capture it.
    """

    invite: InviteRead
    accept_url: str
