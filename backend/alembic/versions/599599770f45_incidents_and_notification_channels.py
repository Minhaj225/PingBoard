"""incidents and notification channels

Revision ID: 599599770f45
Revises: eba9ef492eb4
Create Date: 2026-10-05 12:15:13.266032

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "599599770f45"
down_revision: str | None = "eba9ef492eb4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum types are created and dropped explicitly. An implicit CREATE TYPE from a
# column definition is never paired with a DROP TYPE on downgrade, which orphans
# the type and breaks the next upgrade.
channel_type = postgresql.ENUM("email", "slack", "discord", name="channel_type", create_type=False)
incident_severity = postgresql.ENUM(
    "minor", "major", "critical", name="incident_severity", create_type=False
)


def upgrade() -> None:
    channel_type.create(op.get_bind(), checkfirst=False)
    incident_severity.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "notification_channels",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", channel_type, nullable=False),
        sa.Column(
            "config", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_channels_org_id"), "notification_channels", ["org_id"], unique=False
    )
    op.create_table(
        "incidents",
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("severity", incident_severity, server_default="major", nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incidents_monitor_started", "incidents", ["monitor_id", "started_at"], unique=False
    )
    op.create_index(
        "uq_incidents_one_open_per_monitor",
        "incidents",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_table(
        "incident_updates",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("is_auto", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_incident_updates_incident_id"), "incident_updates", ["incident_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_incident_updates_incident_id"), table_name="incident_updates")
    op.drop_table("incident_updates")
    op.drop_index(
        "uq_incidents_one_open_per_monitor",
        table_name="incidents",
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.drop_index("ix_incidents_monitor_started", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index(op.f("ix_notification_channels_org_id"), table_name="notification_channels")
    op.drop_table("notification_channels")

    incident_severity.drop(op.get_bind(), checkfirst=False)
    channel_type.drop(op.get_bind(), checkfirst=False)
