"""User and refresh-token models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.orgs.models import Membership


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Stored lowercased; the unique index is therefore case-insensitive in
    # practice without needing CITEXT.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))

    # Null for accounts created purely through OAuth.
    password_hash: Mapped[str | None] = mapped_column(String(128))
    github_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    # `lazy="raise"` because `get_current_user` loads a User on every request:
    # an eager strategy here would add a query per request for collections that
    # are always fetched explicitly instead. Deletes are left to the database's
    # ON DELETE CASCADE (`passive_deletes`) rather than loading children first.
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete", passive_deletes=True, lazy="raise"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete", passive_deletes=True, lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class RefreshToken(UUIDMixin, TimestampMixin, Base):
    """One row per issued refresh token.

    Tokens are rotated on every use: the presented row is revoked and a fresh
    one issued. Rows are kept after revocation so that replay of an already-used
    token can be detected (see `app.auth.tokens.rotate_refresh_token`).
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_id_revoked_at", "user_id", "revoked_at"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 hex digest of the raw token; the raw value is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
