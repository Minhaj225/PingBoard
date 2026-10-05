"""Organization, membership and invite operations."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.auth.service import normalize_email
from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token
from app.orgs.models import MemberRole, Membership, Organization, OrgInvite

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
SLUG_MAX_LENGTH = 80


class SlugTaken(Exception):
    """The requested slug is already in use."""


class AlreadyMember(Exception):
    """The user already belongs to this organization."""


class InviteInvalid(Exception):
    """The invite token is unknown, expired, or already accepted."""


class InviteEmailMismatch(Exception):
    """The invite was addressed to a different email address."""


def slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    )
    # Strip again after truncating: cutting at 80 can land on a separator.
    return _SLUG_STRIP.sub("-", ascii_value).strip("-")[:SLUG_MAX_LENGTH].strip("-") or "org"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    """Append a numeric suffix until the slug is free.

    A concurrent create could still collide; the unique constraint is the real
    guarantee and the endpoint maps that violation to a 409.
    """
    candidate = base
    suffix = 2
    while await db.scalar(select(Organization.id).where(Organization.slug == candidate)):
        candidate = f"{base[: SLUG_MAX_LENGTH - 6].strip('-')}-{suffix}"
        suffix += 1
    return candidate


async def create_organization(
    db: AsyncSession, *, name: str, owner: User, slug: str | None = None
) -> Organization:
    """Create an org and make `owner` its first member."""
    if slug is not None:
        if await db.scalar(select(Organization.id).where(Organization.slug == slug)):
            raise SlugTaken(slug)
        final_slug = slug
    else:
        final_slug = await _unique_slug(db, slugify(name))

    org = Organization(name=name, slug=final_slug)
    db.add(org)
    await db.flush()

    db.add(Membership(org_id=org.id, user_id=owner.id, role=MemberRole.OWNER))
    await db.flush()
    return org


async def list_memberships(db: AsyncSession, user: User) -> list[Membership]:
    result = await db.scalars(
        select(Membership)
        .where(Membership.user_id == user.id)
        .options(selectinload(Membership.organization))
        .order_by(Membership.created_at)
    )
    return list(result)


async def list_members(db: AsyncSession, org_id: UUID) -> list[Membership]:
    result = await db.scalars(
        select(Membership)
        .where(Membership.org_id == org_id)
        .options(selectinload(Membership.user))
        .order_by(Membership.created_at)
    )
    return list(result)


# --- Invites ---------------------------------------------------------------


async def create_invite(
    db: AsyncSession, *, org_id: UUID, email: str, role: MemberRole, invited_by: User
) -> tuple[OrgInvite, str]:
    """Create an invite and return it with its single-use raw token."""
    settings = get_settings()
    normalized = normalize_email(email)

    existing = await db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id, User.email == normalized)
    )
    if existing is not None:
        raise AlreadyMember(normalized)

    raw, digest = generate_opaque_token()
    invite = OrgInvite(
        org_id=org_id,
        email=normalized,
        role=role,
        token_hash=digest,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.INVITE_EXPIRE_HOURS),
        invited_by=invited_by.id,
    )
    db.add(invite)
    await db.flush()
    return invite, raw


async def accept_invite(db: AsyncSession, *, raw_token: str, user: User) -> Membership:
    """Redeem an invite for `user`, who must already be registered.

    The invite is bound to the address it was sent to, so a leaked link cannot
    be redeemed by whoever happens to find it.
    """
    invite = await db.scalar(
        select(OrgInvite).where(OrgInvite.token_hash == hash_opaque_token(raw_token))
    )
    if invite is None or invite.accepted_at is not None:
        raise InviteInvalid("unknown or already accepted invite")
    if invite.expires_at <= datetime.now(UTC):
        raise InviteInvalid("invite expired")
    if invite.email != normalize_email(user.email):
        raise InviteEmailMismatch(invite.email)

    membership = await db.scalar(
        select(Membership).where(Membership.org_id == invite.org_id, Membership.user_id == user.id)
    )
    if membership is None:
        membership = Membership(org_id=invite.org_id, user_id=user.id, role=invite.role)
        db.add(membership)

    invite.accepted_at = datetime.now(UTC)
    await db.flush()
    return membership
