"""Organization, membership and invite models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.auth.models import User


class MemberRole(enum.StrEnum):
    """Roles, least to most privileged.

    Comparison is by `RANK` rather than by declaration order so that inserting a
    new role later cannot silently change who is allowed to do what.
    """

    VIEWER = "viewer"
    ADMIN = "admin"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def covers(self, required: MemberRole) -> bool:
        return self.rank >= required.rank


_ROLE_RANK: dict[MemberRole, int] = {
    MemberRole.VIEWER: 1,
    MemberRole.ADMIN: 2,
    MemberRole.OWNER: 3,
}

# Persist the member value ("viewer"), not the Python name ("VIEWER").
role_enum = Enum(
    MemberRole,
    name="member_role",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete", passive_deletes=True, lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class Membership(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),)

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MemberRole] = mapped_column(role_enum, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class OrgInvite(UUIDMixin, TimestampMixin, Base):
    """A pending invitation to join an organization.

    Like refresh tokens, only a digest of the invite token is stored: the raw
    value exists solely in the invitation link sent to the invitee.
    """

    __tablename__ = "org_invites"

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[MemberRole] = mapped_column(role_enum, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    organization: Mapped[Organization] = relationship()
