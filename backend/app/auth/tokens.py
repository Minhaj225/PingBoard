"""Refresh-token issuance, rotation and revocation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken
from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token

logger = logging.getLogger(__name__)


class RefreshTokenError(Exception):
    """The presented refresh token is unusable."""


async def issue_refresh_token(db: AsyncSession, user_id: UUID) -> str:
    """Create a new refresh token row and return the raw value for the cookie."""
    settings = get_settings()
    raw, digest = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=digest,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.flush()
    return raw


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[UUID, str]:
    """Consume `raw_token` and return `(user_id, new_raw_token)`.

    Rotation is single-use. If a token that was already rotated (or explicitly
    revoked) is presented again, that is either a replay or a stolen cookie, so
    every outstanding token for the user is revoked and the caller is forced to
    log in again.
    """
    digest = hash_opaque_token(raw_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))

    if stored is None:
        raise RefreshTokenError("unknown refresh token")

    now = datetime.now(UTC)

    if stored.revoked_at is not None:
        logger.warning(
            "refresh token reuse detected; revoking all sessions",
            extra={"user_id": str(stored.user_id)},
        )
        await revoke_all_for_user(db, stored.user_id)
        raise RefreshTokenError("refresh token already used")

    if stored.expires_at <= now:
        raise RefreshTokenError("refresh token expired")

    stored.revoked_at = now
    new_raw = await issue_refresh_token(db, stored.user_id)
    return stored.user_id, new_raw


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a single token. Unknown or already-revoked tokens are a no-op."""
    digest = hash_opaque_token(raw_token)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == digest, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
