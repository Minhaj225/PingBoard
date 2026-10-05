"""Authentication dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.db import get_db
from app.core.security import InvalidToken, decode_access_token

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False so a missing header produces our own 401 with a
# WWW-Authenticate challenge rather than FastAPI's bare 403.
_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise _UNAUTHENTICATED

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidToken as exc:
        raise _UNAUTHENTICATED from exc

    user = await db.get(User, payload.sub)
    if user is None:
        # Token is validly signed but the account is gone.
        raise _UNAUTHENTICATED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
