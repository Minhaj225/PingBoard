"""Single import surface for every ORM model.

Alembic's `env.py` imports this module so that `Base.metadata` is fully
populated before autogenerate runs. Add each new model module here.
"""

from __future__ import annotations

from app.auth.models import RefreshToken, User
from app.channels.models import NotificationChannel
from app.core.db import Base
from app.incidents.models import Incident, IncidentUpdate
from app.monitors.models import CheckResult, Monitor
from app.monitors.rollup_models import RollupHourly
from app.orgs.api_keys import ApiKey
from app.orgs.models import Membership, Organization, OrgInvite
from app.status_pages.models import StatusPage

__all__ = [
    "ApiKey",
    "Base",
    "CheckResult",
    "Incident",
    "IncidentUpdate",
    "Membership",
    "Monitor",
    "NotificationChannel",
    "OrgInvite",
    "Organization",
    "RefreshToken",
    "RollupHourly",
    "StatusPage",
    "User",
]
