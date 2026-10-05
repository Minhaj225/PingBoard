"""Status page models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.mixins import TimestampMixin, UUIDMixin
from app.monitors.models import Monitor

# Association table rather than an array column: a real foreign key means a
# deleted monitor cannot linger as a dangling id on a published page.
status_page_monitors = Table(
    "status_page_monitors",
    Base.metadata,
    Column(
        "status_page_id",
        Uuid,
        ForeignKey("status_pages.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "monitor_id",
        Uuid,
        ForeignKey("monitors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class StatusPage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "status_pages"

    org_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    # A page can be taken offline without deleting it and losing the slug.
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    monitors: Mapped[list[Monitor]] = relationship(
        secondary=status_page_monitors, lazy="raise", order_by=Monitor.name
    )
