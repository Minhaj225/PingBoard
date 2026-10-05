"""Organization endpoints."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.auth.deps import CurrentUser, DbSession
from app.core.config import Settings, get_settings
from app.core.mail import send_email
from app.orgs import service
from app.orgs.deps import RequireAdmin, RequireViewer
from app.orgs.schemas import (
    InviteCreate,
    InviteCreated,
    InviteRead,
    MemberRead,
    OrgCreate,
    OrgRead,
    OrgSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orgs", tags=["orgs"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "",
    response_model=OrgRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization owned by the caller",
)
async def create_org(payload: OrgCreate, user: CurrentUser, db: DbSession) -> OrgRead:
    try:
        org = await service.create_organization(
            db, name=payload.name, slug=payload.slug, owner=user
        )
        await db.commit()
    except service.SlugTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That slug is already taken"
        ) from exc
    except IntegrityError as exc:
        # Lost a race against a concurrent create with the same slug.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That slug is already taken"
        ) from exc

    return OrgRead.model_validate(org)


@router.get("", response_model=list[OrgSummary], summary="Organizations the caller belongs to")
async def list_orgs(user: CurrentUser, db: DbSession) -> list[OrgSummary]:
    memberships = await service.list_memberships(db, user)
    return [
        OrgSummary(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            created_at=m.organization.created_at,
            role=m.role,
        )
        for m in memberships
    ]


@router.get(
    "/{org_id}/members",
    response_model=list[MemberRead],
    summary="List members of an organization",
)
async def list_members(
    org_id: UUID,
    db: DbSession,
    _membership: RequireViewer,
) -> list[MemberRead]:
    members = await service.list_members(db, org_id)
    return [
        MemberRead(
            user_id=m.user.id,
            email=m.user.email,
            name=m.user.name,
            role=m.role,
            joined_at=m.created_at,
        )
        for m in members
    ]


@router.post(
    "/{org_id}/invite",
    response_model=InviteCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone to an organization",
)
async def invite_member(
    org_id: UUID,
    payload: InviteCreate,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    membership: RequireAdmin,
) -> InviteCreated:
    """Admins may invite; only an owner may hand out the owner role."""
    if payload.role.rank > membership.role.rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot grant a role above your own",
        )

    try:
        invite, raw_token = await service.create_invite(
            db, org_id=org_id, email=payload.email, role=payload.role, invited_by=user
        )
    except service.AlreadyMember as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That person is already a member of this organization",
        ) from exc

    accept_url = f"{settings.FRONTEND_URL}/invites/{raw_token}"
    await db.commit()

    await send_email(
        to=invite.email,
        subject="You have been invited to a PingBoard organization",
        body=(
            f"{user.name or user.email} invited you to join an organization on PingBoard "
            f"as {invite.role.value}.\n\nAccept the invitation:\n{accept_url}\n\n"
            f"This link expires in {settings.INVITE_EXPIRE_HOURS} hours."
        ),
    )

    return InviteCreated(invite=InviteRead.model_validate(invite), accept_url=accept_url)


@router.post(
    "/invites/{token}/accept",
    response_model=OrgSummary,
    summary="Accept an invitation",
)
async def accept_invite(token: str, user: CurrentUser, db: DbSession) -> OrgSummary:
    try:
        membership = await service.accept_invite(db, raw_token=token, user=user)
    except service.InviteInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This invitation is invalid or has expired",
        ) from exc
    except service.InviteEmailMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address",
        ) from exc

    await db.commit()
    await db.refresh(membership, ["organization"])
    org = membership.organization
    return OrgSummary(
        id=org.id, name=org.name, slug=org.slug, created_at=org.created_at, role=membership.role
    )
