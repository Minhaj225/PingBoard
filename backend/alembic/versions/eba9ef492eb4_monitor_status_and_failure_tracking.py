"""monitor status and failure tracking

Revision ID: eba9ef492eb4
Revises: ef5ade420c6e
Create Date: 2026-10-05 11:58:35.634384

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "eba9ef492eb4"
down_revision: str | None = "ef5ade420c6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Created and dropped explicitly: an implicit CREATE TYPE from the column
# definition is never paired with a DROP TYPE on downgrade, which orphans the
# type and breaks the next upgrade.
MONITOR_STATUSES = ("unknown", "up", "down")
monitor_status = postgresql.ENUM(*MONITOR_STATUSES, name="monitor_status", create_type=False)


def upgrade() -> None:
    monitor_status.create(op.get_bind(), checkfirst=False)

    op.add_column(
        "monitors", sa.Column("status", monitor_status, server_default="unknown", nullable=False)
    )
    op.add_column(
        "monitors",
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "monitors", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("monitors", "last_checked_at")
    op.drop_column("monitors", "consecutive_failures")
    op.drop_column("monitors", "status")

    monitor_status.drop(op.get_bind(), checkfirst=False)
