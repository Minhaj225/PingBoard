"""API keys for programmatic access.

A key is shown **once**, at creation. Only a SHA-256 digest is stored, so a
database leak does not hand over working credentials, and "show me the key
again" is impossible by construction rather than by policy.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin
from app.core.security import hash_opaque_token

# A recognisable prefix makes a leaked key greppable in logs and lets secret
# scanners spot it. The entropy is in the suffix.
KEY_PREFIX = "pb_"
KEY_BYTES = 32


class ApiKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Shown in the UI so an unused key can be spotted and revoked.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


def generate_key() -> tuple[str, str]:
    """Return `(raw_key, digest)`. The raw key is never persisted."""
    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(KEY_BYTES)}"
    return raw, hash_opaque_token(raw)


async def create_key(db: AsyncSession, *, org_id: UUID, name: str) -> tuple[ApiKey, str]:
    raw, digest = generate_key()
    key = ApiKey(org_id=org_id, name=name, key_hash=digest)
    db.add(key)
    await db.flush()
    return key, raw


async def resolve_key(db: AsyncSession, raw: str) -> ApiKey | None:
    """Look up an active key by its digest and stamp `last_used_at`."""
    if not raw.startswith(KEY_PREFIX):
        return None

    key = await db.scalar(
        select(ApiKey).where(ApiKey.key_hash == hash_opaque_token(raw), ApiKey.revoked_at.is_(None))
    )
    if key is None:
        return None

    key.last_used_at = datetime.now(UTC)
    return key


async def revoke_key(db: AsyncSession, key: ApiKey) -> None:
    """Revoked, not deleted — the audit trail outlives the credential."""
    key.revoked_at = datetime.now(UTC)
    await db.flush()


async def list_keys(db: AsyncSession, org_id: UUID) -> list[ApiKey]:
    return list(
        await db.scalars(
            select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.created_at.desc())
        )
    )
