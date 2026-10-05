"""Organization-scoped authorization."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentUser, DbSession
from app.auth.models import User
from app.orgs.models import MemberRole, Membership


async def get_membership(db: AsyncSession, org_id: UUID, user: User) -> Membership | None:
    return await db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)
    )


def require_role(
    minimum: MemberRole,
) -> Callable[[UUID, User, AsyncSession], Awaitable[Membership]]:
    """Build a dependency asserting the caller's role in the path's `org_id`.

    Returns the caller's `Membership` so handlers can use the authenticated
    role without re-querying. A non-member gets 404 rather than 403: confirming
    that an organization exists is itself a disclosure to an outsider.
    """

    async def dependency(
        org_id: Annotated[UUID, Path()],
        user: CurrentUser,
        db: DbSession,
    ) -> Membership:
        membership = await get_membership(db, org_id, user)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        if not membership.role.covers(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the {minimum.value} role or higher",
            )
        return membership

    return dependency


RequireViewer = Annotated[Membership, Depends(require_role(MemberRole.VIEWER))]
RequireAdmin = Annotated[Membership, Depends(require_role(MemberRole.ADMIN))]
RequireOwner = Annotated[Membership, Depends(require_role(MemberRole.OWNER))]
