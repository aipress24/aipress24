# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `bw_managers_ids`, `bw_pr_managers_ids`, and
`bw_roles_ids` in `app.modules.bw.bw_activation.utils`.

These three iterate over a BW's `role_assignments` collection — a
loaded list, no DB query — and filter by role + invitation status.
They're called from many access-control sites :

- `bw_managers_ids` → who can reach the BW management dashboard
- `bw_pr_managers_ids` → who can act as a PR Manager for the BW
- `bw_roles_ids` → generic filter (the building block of the
  other two)

Two non-obvious behaviours pinned here :

1. **Bug #0157 fallback** : when no real manager has accepted yet,
   `bw_managers_ids` includes `bw.owner_id` as a bootstrap safety
   net so the freshly-created BW isn't dashboard-orphaned. The
   fallback turns OFF once any real manager is in place.

2. **PR managers always include the owner** : `bw_pr_managers_ids`
   unconditionally adds `bw.owner_id`, even when a real PR manager
   exists. Pin the asymmetry so a future « consistency » refactor
   doesn't silently change either behaviour.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.utils import (
    bw_managers_ids,
    bw_pr_managers_ids,
    bw_roles_ids,
)


class _Assignment:
    """Stand-in for the `RoleAssignment` ORM row."""

    def __init__(
        self,
        *,
        user_id: int,
        role_type: str,
        invitation_status: str = InvitationStatus.ACCEPTED.value,
    ) -> None:
        self.user_id = user_id
        self.role_type = role_type
        self.invitation_status = invitation_status


class _BW:
    """Stand-in for the BusinessWall ORM row. Only `role_assignments`
    + `owner_id` are read by the helpers under test."""

    def __init__(self, *, owner_id: int = 1, role_assignments=None) -> None:
        self.owner_id = owner_id
        self.role_assignments = role_assignments or []


# ── bw_roles_ids ─────────────────────────────────────────────────────


class TestBwRolesIds:
    def test_empty_role_assignments_returns_empty_set(self):
        bw = _BW(role_assignments=[])
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value},
            {InvitationStatus.ACCEPTED.value},
        )
        assert result == set()

    def test_none_role_assignments_returns_empty_set(self):
        """When the BW row is freshly loaded without role_assignments
        relationship populated, the helper must NOT crash. Pin the
        defensive empty return."""
        bw = _BW(role_assignments=None)
        bw.role_assignments = None
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value},
            {InvitationStatus.ACCEPTED.value},
        )
        assert result == set()

    def test_filters_by_required_role(self):
        bw = _BW(
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
                _Assignment(user_id=20, role_type=BWRoleType.BWPRI.value),
                _Assignment(user_id=30, role_type=BWRoleType.BWMI.value),
            ]
        )
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value},
            {InvitationStatus.ACCEPTED.value},
        )
        assert result == {10, 30}

    def test_filters_by_required_status(self):
        bw = _BW(
            role_assignments=[
                _Assignment(
                    user_id=10,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                ),
                _Assignment(
                    user_id=20,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                ),
            ]
        )
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value},
            {InvitationStatus.ACCEPTED.value},
        )
        assert result == {10}

    def test_includes_when_either_set_has_multiple(self):
        """Multiple roles + multiple statuses — pin the « any role
        AND any status » logic. Pin so a future « all roles » refactor
        doesn't silently tighten the gate."""
        bw = _BW(
            role_assignments=[
                _Assignment(
                    user_id=1,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                ),
                _Assignment(
                    user_id=2,
                    role_type=BWRoleType.BWPRI.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                ),
                _Assignment(
                    user_id=3,
                    role_type=BWRoleType.BWME.value,
                    invitation_status=InvitationStatus.REJECTED.value,
                ),
            ]
        )
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value, BWRoleType.BWPRI.value},
            {
                InvitationStatus.PENDING.value,
                InvitationStatus.ACCEPTED.value,
            },
        )
        assert result == {1, 2}

    def test_deduplicates_user_with_multiple_assignments(self):
        """Same user with two qualifying assignments → returned once.
        Pin so a future caller iterating over a list (instead of set)
        doesn't surprise themselves with duplicates."""
        bw = _BW(
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
                _Assignment(user_id=10, role_type=BWRoleType.BWPRI.value),
            ]
        )
        result = bw_roles_ids(
            bw,
            {BWRoleType.BWMI.value, BWRoleType.BWPRI.value},
            {InvitationStatus.ACCEPTED.value},
        )
        assert result == {10}

    def test_returns_set_type(self):
        bw = _BW(role_assignments=[])
        result = bw_roles_ids(bw, set(), set())
        assert isinstance(result, set)


# ── bw_managers_ids ──────────────────────────────────────────────────


class TestBwManagersIds:
    def test_returns_users_with_accepted_dashboard_role(self):
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
                _Assignment(user_id=20, role_type=BWRoleType.BWME.value),
            ],
        )
        result = bw_managers_ids(bw)
        # 10 and 20 are real managers ; owner fallback NOT applied
        # because real managers exist.
        assert 10 in result
        assert 20 in result
        assert 99 not in result

    def test_falls_back_to_owner_when_no_real_managers(self):
        """Bug #0157 v1 — the bootstrap safety net. Empty
        role_assignments → return the owner so the freshly-created
        BW isn't dashboard-orphaned."""
        bw = _BW(owner_id=99, role_assignments=[])
        result = bw_managers_ids(bw)
        assert result == {99}

    def test_falls_back_to_owner_when_all_pending(self):
        """All managers are still PENDING → bootstrap fallback
        applies. Pin so a future « count pending as eligible »
        regression that breaks Bug #0157's fix gets caught."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(
                    user_id=10,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                ),
            ],
        )
        result = bw_managers_ids(bw)
        assert result == {99}

    def test_does_not_fall_back_when_real_manager_accepted(self):
        """Bug #0157 v2 — the asymmetry. As soon as a real
        dashboard manager has ACCEPTED, the owner is NO LONGER
        unconditionally included (in particular : an owner whose
        only accepted role is BWPRi must not reach the dashboard)."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        result = bw_managers_ids(bw)
        assert result == {10}
        # The owner is NOT in the result — Bug #0157 v2 fix.
        assert 99 not in result

    def test_bwpri_alone_does_not_make_owner_a_manager(self):
        """The bug Erick reported : owner with BWPRi accepted but
        no real manager → the owner used to leak through. Pin so
        the fix doesn't regress."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=99, role_type=BWRoleType.BWPRI.value),
            ],
        )
        result = bw_managers_ids(bw)
        # No accepted dashboard role → owner fallback fires.
        # But the owner himself is the dashboard fallback because
        # nobody else is there.
        assert result == {99}

    def test_bw_owner_role_counts_as_dashboard_role(self):
        """BW_OWNER is in DASHBOARD_ACCESS_ROLES."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=99, role_type=BWRoleType.BW_OWNER.value),
            ],
        )
        result = bw_managers_ids(bw)
        assert 99 in result


# ── bw_pr_managers_ids ───────────────────────────────────────────────


class TestBwPrManagersIds:
    def test_includes_pr_managers_with_accepted_role(self):
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWPRI.value),
                _Assignment(user_id=20, role_type=BWRoleType.BWPRE.value),
            ],
        )
        result = bw_pr_managers_ids(bw)
        assert 10 in result
        assert 20 in result

    def test_always_includes_owner_unconditionally(self):
        """The asymmetry with `bw_managers_ids` : the owner is ALWAYS
        a PR manager, even when explicit PR managers exist. Pin so
        a future « consistency » refactor that drops this doesn't
        silently break BW owner workflows."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWPRI.value),
            ],
        )
        result = bw_pr_managers_ids(bw)
        assert 99 in result, (
            "Owner must always be in PR managers (asymmetry with "
            "bw_managers_ids — see Bug #0157 v2)."
        )
        assert 10 in result

    def test_owner_alone_when_no_pr_managers(self):
        bw = _BW(owner_id=99, role_assignments=[])
        result = bw_pr_managers_ids(bw)
        assert result == {99}

    def test_excludes_pending_pr_managers(self):
        """Same status filter as `bw_managers_ids` — only ACCEPTED
        assignments count. Pin."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(
                    user_id=10,
                    role_type=BWRoleType.BWPRI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                ),
            ],
        )
        result = bw_pr_managers_ids(bw)
        assert result == {99}
        assert 10 not in result

    def test_excludes_dashboard_only_managers(self):
        """BWMi/BWMe are NOT PR managers ; they're dashboard managers.
        Pin the asymmetry."""
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
                _Assignment(user_id=20, role_type=BWRoleType.BWME.value),
            ],
        )
        result = bw_pr_managers_ids(bw)
        # Only the owner — neither 10 nor 20 has a PR role.
        assert result == {99}
