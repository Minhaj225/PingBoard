from __future__ import annotations

import pytest

from app.orgs.models import MemberRole


class TestRoleOrdering:
    def test_ranks_are_strictly_increasing(self) -> None:
        assert MemberRole.VIEWER.rank < MemberRole.ADMIN.rank < MemberRole.OWNER.rank

    @pytest.mark.parametrize(
        ("actual", "required", "expected"),
        [
            (MemberRole.OWNER, MemberRole.OWNER, True),
            (MemberRole.OWNER, MemberRole.ADMIN, True),
            (MemberRole.OWNER, MemberRole.VIEWER, True),
            (MemberRole.ADMIN, MemberRole.OWNER, False),
            (MemberRole.ADMIN, MemberRole.ADMIN, True),
            (MemberRole.ADMIN, MemberRole.VIEWER, True),
            (MemberRole.VIEWER, MemberRole.OWNER, False),
            (MemberRole.VIEWER, MemberRole.ADMIN, False),
            (MemberRole.VIEWER, MemberRole.VIEWER, True),
        ],
    )
    def test_covers(self, actual: MemberRole, required: MemberRole, expected: bool) -> None:
        assert actual.covers(required) is expected

    def test_every_role_has_a_rank(self) -> None:
        """A new role added without a rank must fail loudly, not sort as 0."""
        for role in MemberRole:
            assert role.rank > 0

    def test_serializes_to_lowercase_value(self) -> None:
        assert MemberRole.OWNER == "owner"
        assert str(MemberRole.VIEWER) == "viewer"
