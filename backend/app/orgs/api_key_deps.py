"""Authenticating with an API key instead of a JWT.

Lets a CI job or a script drive the API without a browser session. A key grants
**admin** rights within exactly one organization — it is not a user, so it can
never be used to read another org or to touch account-level endpoints like
`/auth/*`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import DbSession, get_current_user
from app.auth.models import User
from app.core.db import get_db
from app.orgs import api_keys
from app.orgs.deps import get_membership
from app.orgs.models import MemberRole, Membership

API_KEY_HEADER = "X-API-Key"


@dataclass(frozen=True)
class Principal:
    """Whoever is making the request — a signed-in user or an API key."""

    org_id: UUID
    role: MemberRole
    user: User | None
    via_api_key: bool

    def covers(self, minimum: MemberRole) -> bool:
        return self.role.covers(minimum)


_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="This API key cannot access that organization"
)
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


async def principal_from_api_key(db: AsyncSession, raw_key: str, org_id: UUID) -> Principal:
    key = await api_keys.resolve_key(db, raw_key)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )

    # The key's own org is authoritative; an org_id in the request is only a
    # lookup, and a mismatch is a hard refusal rather than a silent override.
    if key.org_id != org_id:
        raise _FORBIDDEN

    await db.commit()  # persist last_used_at
    return Principal(org_id=key.org_id, role=MemberRole.ADMIN, user=None, via_api_key=True)


async def require_api_key_or_jwt(
    db: DbSession,
    org_id: Annotated[UUID, Query(description="Organization that owns the resource")],
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Accept either an API key or a bearer token.

    The key is checked first so a script sending both does not silently depend
    on which one the server happened to prefer.
    """
    if api_key:
        return await principal_from_api_key(db, api_key, org_id)

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide a bearer token or an X-API-Key header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await _user_from_bearer(db, authorization)
    membership: Membership | None = await get_membership(db, org_id, user)
    if membership is None:
        raise _NOT_FOUND

    return Principal(org_id=org_id, role=membership.role, user=user, via_api_key=False)


async def _user_from_bearer(db: AsyncSession, authorization: str) -> User:
    from fastapi.security import HTTPAuthorizationCredentials

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await get_current_user(
        db, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )


def require_principal(
    minimum: MemberRole,
) -> Callable[[Principal], Awaitable[Principal]]:
    """Build a dependency asserting the principal's role."""

    async def dependency(
        principal: Annotated[Principal, Depends(require_api_key_or_jwt)],
    ) -> Principal:
        if not principal.covers(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the {minimum.value} role or higher",
            )
        return principal

    return dependency


ScriptableAdmin = Annotated[Principal, Depends(require_principal(MemberRole.ADMIN))]

__all__ = ["API_KEY_HEADER", "Principal", "ScriptableAdmin", "get_db", "require_principal"]
