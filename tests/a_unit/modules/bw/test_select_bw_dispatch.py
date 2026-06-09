# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the role dispatch tables in
`app.modules.bw.bw_activation.routes.select_bw`.

The `/select-bw` route handlers route a user to one of three places
based on the roles they hold on the selected Business Wall:

- management role (BW_OWNER / BWMi / BWMe) -> BW dashboard
- PR role (BWPRi / BWPRe)                  -> Com'room (wip.comroom)
- no role at all                           -> not_authorized page

The full route handlers are Flask-/DB-coupled and live in the
integration tier, but the **dispatch contract** itself is pure: it
is encoded in the two module-level frozensets `_MANAGEMENT_ROLES`
and `_PR_ROLES`. Those sets are what bug #0166 (Erick, 2026-06-02)
was about — non-managers used to fall through to a silent re-render
because no role bucket claimed them. Pinning the buckets here makes
sure a future cleanup of BWRoleType members doesn't accidentally drop
one of the active roles or merge the management / PR distinction.

We also pin the predicate that the handler applies on top of the sets
(role match AND `invitation_status == ACCEPTED`) by reimplementing it
against the same imported constants with stand-in role-assignment
rows — the assignment matrix is small enough to exhaustively cover.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.routes.select_bw import (
    _MANAGEMENT_ROLES,
    _PR_ROLES,
)


# Stand-in row mimicking a SQLAlchemy RoleAssignment — duck-typed to
# the three attributes the select_bw handler reads.
@dataclass
class _Assignment:
    user_id: int
    role_type: str
    invitation_status: str


class TestManagementRolesSet:
    """Pin which roles count as « can manage this BW ».

    The handler routes users with any role in `_MANAGEMENT_ROLES` to
    the BW dashboard (full management UI). Adding or removing a member
    from this set silently changes who can reach the dashboard, so
    every transition deserves a deliberate test update.
    """

    def test_contains_bw_owner(self) -> None:
        assert BWRoleType.BW_OWNER.value in _MANAGEMENT_ROLES

    def test_contains_internal_manager(self) -> None:
        assert BWRoleType.BWMI.value in _MANAGEMENT_ROLES

    def test_contains_external_manager(self) -> None:
        assert BWRoleType.BWME.value in _MANAGEMENT_ROLES

    def test_excludes_pr_roles(self) -> None:
        """PR managers (BWPRi / BWPRe) are publication-oriented and
        must NOT reach the dashboard — bug #0166 was caused by them
        being silently bucketed into the management path.
        """
        assert BWRoleType.BWPRI.value not in _MANAGEMENT_ROLES
        assert BWRoleType.BWPRE.value not in _MANAGEMENT_ROLES

    def test_is_frozen(self) -> None:
        """Mutation guard: the dispatch table is a module-level
        constant; making it mutable would let a request handler
        accidentally rewrite the RBAC rules at runtime.
        """
        assert isinstance(_MANAGEMENT_ROLES, frozenset)

    def test_size_is_exactly_three(self) -> None:
        assert len(_MANAGEMENT_ROLES) == 3


class TestPrRolesSet:
    """Pin which roles count as « PR manager, redirect to Com'room ».

    Bug #0166 fix (Erick, 2026-06-02): non-management roles must
    resolve to a non-empty dispatch bucket so the handler can
    redirect somewhere meaningful instead of re-rendering the
    selector. `_PR_ROLES` is that bucket.
    """

    def test_contains_internal_pr(self) -> None:
        assert BWRoleType.BWPRI.value in _PR_ROLES

    def test_contains_external_pr(self) -> None:
        assert BWRoleType.BWPRE.value in _PR_ROLES

    def test_excludes_management_roles(self) -> None:
        for role in (BWRoleType.BW_OWNER, BWRoleType.BWMI, BWRoleType.BWME):
            assert role.value not in _PR_ROLES

    def test_is_frozen(self) -> None:
        assert isinstance(_PR_ROLES, frozenset)

    def test_size_is_exactly_two(self) -> None:
        assert len(_PR_ROLES) == 2


class TestDispatchPartition:
    """Pin the partition: every defined BWRoleType is assigned to
    exactly one bucket, and the buckets are disjoint.

    If somebody adds a new role to BWRoleType, this test forces them
    to decide *explicitly* which bucket it belongs to — otherwise the
    handler will silently drop holders of the new role into the
    « no role » branch and they'll hit `not_authorized`.
    """

    def test_buckets_are_disjoint(self) -> None:
        assert _MANAGEMENT_ROLES.isdisjoint(_PR_ROLES)

    def test_buckets_cover_every_defined_role(self) -> None:
        all_roles = {r.value for r in BWRoleType}
        bucketed = _MANAGEMENT_ROLES | _PR_ROLES
        assert all_roles == bucketed, (
            f"Unbucketed roles would silently land on /not_authorized: "
            f"{all_roles - bucketed}"
        )


def _classify(
    assignments: list[_Assignment],
    user_id: int,
    owner_id: int,
) -> tuple[bool, bool]:
    """Reimplementation of the predicate the handler applies on top
    of the dispatch sets — see `select_bw_post`. Kept here so the
    parametrized matrix below exercises *exactly* the same constants
    (`_MANAGEMENT_ROLES`, `_PR_ROLES`, `InvitationStatus.ACCEPTED`)
    that the production handler does.
    """
    has_management = False
    has_pr = False
    if owner_id == user_id:
        return True, False
    for a in assignments:
        if (
            a.user_id == user_id
            and a.invitation_status == InvitationStatus.ACCEPTED.value
        ):
            if a.role_type in _MANAGEMENT_ROLES:
                has_management = True
            elif a.role_type in _PR_ROLES:
                has_pr = True
    return has_management, has_pr


class TestPredicateContract:
    """Pin the role-+-status predicate that the handler composes
    with the dispatch sets.

    The handler grants rights only when role membership AND
    `invitation_status == ACCEPTED` both hold — a pending / rejected /
    expired invitation must NOT be enough. These tests also pin the
    BW-owner short-circuit (owner needs no role row).
    """

    def test_owner_short_circuit_wins(self) -> None:
        """Owner always has management rights, even with no role row."""
        mgmt, pr = _classify(assignments=[], user_id=1, owner_id=1)
        assert mgmt is True
        assert pr is False

    @pytest.mark.parametrize(
        ("role", "expected_mgmt", "expected_pr"),
        [
            (BWRoleType.BW_OWNER.value, True, False),
            (BWRoleType.BWMI.value, True, False),
            (BWRoleType.BWME.value, True, False),
            (BWRoleType.BWPRI.value, False, True),
            (BWRoleType.BWPRE.value, False, True),
        ],
    )
    def test_accepted_role_routes_to_correct_bucket(
        self,
        role: str,
        expected_mgmt: bool,
        expected_pr: bool,
    ) -> None:
        assignments = [
            _Assignment(
                user_id=7,
                role_type=role,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        ]
        mgmt, pr = _classify(assignments, user_id=7, owner_id=999)
        assert mgmt is expected_mgmt
        assert pr is expected_pr

    @pytest.mark.parametrize(
        "status",
        [
            InvitationStatus.PENDING.value,
            InvitationStatus.REJECTED.value,
            InvitationStatus.EXPIRED.value,
        ],
    )
    def test_non_accepted_status_grants_no_rights(self, status: str) -> None:
        """A role with the right type but a non-accepted invitation
        must not unlock management or PR rights — otherwise an expired
        invitation would still hand out the dashboard.
        """
        assignments = [
            _Assignment(
                user_id=7, role_type=BWRoleType.BWMI.value, invitation_status=status
            )
        ]
        mgmt, pr = _classify(assignments, user_id=7, owner_id=999)
        assert mgmt is False
        assert pr is False

    def test_other_users_rows_are_ignored(self) -> None:
        """Rows for a different user must not leak rights to the
        caller — the user_id filter is what stops cross-user grants.
        """
        assignments = [
            _Assignment(
                user_id=42,
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        ]
        mgmt, pr = _classify(assignments, user_id=7, owner_id=999)
        assert mgmt is False
        assert pr is False

    def test_dual_role_user_gets_both_buckets(self) -> None:
        """A user holding both a management role and a PR role on
        the same BW should be detected as having both — the handler
        then prefers management (dashboard) over PR (Com'room).
        """
        assignments = [
            _Assignment(
                user_id=7,
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            ),
            _Assignment(
                user_id=7,
                role_type=BWRoleType.BWPRE.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            ),
        ]
        mgmt, pr = _classify(assignments, user_id=7, owner_id=999)
        assert mgmt is True
        assert pr is True

    def test_no_matching_row_yields_no_rights(self) -> None:
        """The « not authorized » branch: user has no row at all on
        this BW, so neither bucket fires and the handler will redirect
        to not_authorized (this is what fixes the « clic ne fait rien »
        symptom of #0166).
        """
        mgmt, pr = _classify(assignments=[], user_id=7, owner_id=999)
        assert mgmt is False
        assert pr is False
