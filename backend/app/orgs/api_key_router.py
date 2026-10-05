"""API key management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth.deps import DbSession
from app.orgs import api_keys
from app.orgs.api_keys import ApiKey
from app.orgs.deps import RequireAdmin
from app.orgs.scope import OrgOwner

router = APIRouter(tags=["api keys"])


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(BaseModel):
    """The only response that ever contains the raw key."""

    key: ApiKeyRead
    secret: str = Field(
        description="Shown once. Only a hash is stored, so it cannot be retrieved again."
    )


@router.post(
    "/orgs/{org_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key (the secret is shown exactly once)",
)
async def create_api_key(
    org_id: UUID,
    payload: ApiKeyCreate,
    db: DbSession,
    _membership: RequireAdmin,
) -> ApiKeyCreated:
    key, raw = await api_keys.create_key(db, org_id=org_id, name=payload.name)
    await db.commit()
    return ApiKeyCreated(key=ApiKeyRead.model_validate(key), secret=raw)


@router.get(
    "/orgs/{org_id}/api-keys",
    response_model=list[ApiKeyRead],
    summary="List API keys (never their secrets)",
)
async def list_api_keys(org_id: UUID, db: DbSession, _membership: RequireAdmin) -> list[ApiKeyRead]:
    keys = await api_keys.list_keys(db, org_id)
    return [ApiKeyRead.model_validate(key) for key in keys]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: Annotated[UUID, Path()],
    db: DbSession,
    membership: OrgOwner,
) -> Response:
    """Owner-only, and scoped by org via the `org_id` query parameter, so a
    guessed key id belonging to another tenant 404s rather than being revoked."""
    key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == membership.org_id)
    )
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    await api_keys.revoke_key(db, key)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
