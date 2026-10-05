"""Org scoping for collection endpoints.

Routes like `GET /monitors` need to know *which* organization to list. The
`org_id` travels as a query parameter, but it is only ever a lookup key: the
membership row it resolves to is what actually authorizes the request, and a
caller who is not a member gets 404 rather than 403.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from app.auth.deps import CurrentUser, DbSession
from app.auth.models import User
from app.orgs.deps import get_membership
from app.orgs.models import MemberRole, Membership


def require_org_scope(
    minimum: MemberRole,
) -> Callable[[UUID, User, DbSession], Awaitable[Membership]]:
    async def dependency(
        org_id: Annotated[UUID, Query(description="Organization that owns the resource")],
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


OrgViewer = Annotated[Membership, Depends(require_org_scope(MemberRole.VIEWER))]
OrgAdmin = Annotated[Membership, Depends(require_org_scope(MemberRole.ADMIN))]
OrgOwner = Annotated[Membership, Depends(require_org_scope(MemberRole.OWNER))]
