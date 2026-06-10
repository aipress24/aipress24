# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure decision core of BW invitation orchestration.

`invite_user_role`, `revoke_user_role` and `ensure_roles_membership`
each touch `db.session`, send emails and post in-app notifications,
which makes them hard to test in isolation. But each has a *pure
decision* embedded in it :

- `decide_invite_outcome` : given the BW's already-loaded role
  assignments, the user's active flag, and org membership state,
  what should the shell DO (create / resurrect / no-op / fail) and
  what admin-facing `InvitationOutcomeCode` should bubble up?
- `decide_revoke_action` : given the role assignments list and a
  `(user, role)` pair, *which row* (if any) qualifies for deletion?
- `select_non_member_assignments` : given the role assignments and
  the current org member ids, *which rows* should be revoked because
  the user is no longer a member?

Pinning these three functions catches every regression that matters :
the order of failure checks, the idempotency rules (PENDING /
ACCEPTED stay idempotent, REJECTED / EXPIRED get resurrected), the
external/internal split, and the membership-pruning policy. The
3-line I/O shell that mutates `db.session` afterwards is covered by
integration tests in `tests/b_integration/modules/bw/`.

No test doubles, no patching — only plain stand-in dataclasses
for the RoleAssignment row. Project rule (CLAUDE.md) : « Don't
use mocks. »
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcomeCode,
    InviteAction,
    InviteDecision,
    decide_invite_outcome,
    decide_revoke_action,
    select_non_member_assignments,
)
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus


@dataclass
class StubAssignment:
    """Stand-in for a RoleAssignment row.

    Only the three attributes the decision functions read are
    modelled. Using a plain dataclass keeps the test free of any
    SQLAlchemy machinery.
    """

    user_id: int
    role_type: str
    invitation_status: str = InvitationStatus.PENDING.value
    label: str = ""  # so assertions can identify which row was picked


def _accepted(user_id: int, role: str = BWRoleType.BWMI.value) -> StubAssignment:
    return StubAssignment(user_id, role, InvitationStatus.ACCEPTED.value, "accepted")


def _pending(user_id: int, role: str = BWRoleType.BWMI.value) -> StubAssignment:
    return StubAssignment(user_id, role, InvitationStatus.PENDING.value, "pending")


def _rejected(user_id: int, role: str = BWRoleType.BWMI.value) -> StubAssignment:
    return StubAssignment(user_id, role, InvitationStatus.REJECTED.value, "rejected")


def _expired(user_id: int, role: str = BWRoleType.BWMI.value) -> StubAssignment:
    return StubAssignment(user_id, role, InvitationStatus.EXPIRED.value, "expired")


def _invite(
    *,
    role_assignments=None,
    user_id: int = 1,
    user_active: bool = True,
    role_value: str = BWRoleType.BWMI.value,
    is_internal: bool = True,
    has_org: bool = True,
    user_in_org: bool = True,
) -> InviteDecision:
    """Tiny call-site shim. Keeps the test bodies focused on
    *which input changed* and *what changed in the decision*."""
    return decide_invite_outcome(
        role_assignments=role_assignments or [],
        user_id=user_id,
        user_active=user_active,
        role_value=role_value,
        is_internal=is_internal,
        has_org=has_org,
        user_in_org=user_in_org,
    )


class TestDecideInviteOutcomeFailures:
    """The failure family must short-circuit in spec'd order.

    Bug #0139 v2 is the reason failure paths return distinct codes —
    flashing the right message to the admin is the whole point of
    the value-object refactor."""

    def test_inactive_user_fails_inactive(self):
        decision = _invite(user_active=False)
        assert decision.action == InviteAction.FAIL
        assert decision.outcome_code == InvitationOutcomeCode.FAILED_INACTIVE
        assert decision.existing is None

    def test_inactive_short_circuits_before_org_check(self):
        """Even with no org, the inactive code wins. Pins the order."""
        decision = _invite(user_active=False, has_org=False, user_in_org=False)
        assert decision.outcome_code == InvitationOutcomeCode.FAILED_INACTIVE

    def test_internal_role_without_org_fails_no_org(self):
        decision = _invite(has_org=False, user_in_org=False)
        assert decision.action == InviteAction.FAIL
        assert decision.outcome_code == InvitationOutcomeCode.FAILED_NO_ORG

    def test_internal_role_user_not_in_org_fails_not_in_org(self):
        decision = _invite(has_org=True, user_in_org=False)
        assert decision.action == InviteAction.FAIL
        assert decision.outcome_code == InvitationOutcomeCode.FAILED_NOT_IN_ORG

    def test_external_role_skips_org_checks_entirely(self):
        """`is_internal=False` lets the decision proceed even with
        no org and the user not being a member — the partnership
        flow is the external-role path."""
        decision = _invite(is_internal=False, has_org=False, user_in_org=False)
        assert decision.action == InviteAction.CREATE_NEW
        assert decision.outcome_code == InvitationOutcomeCode.CREATED


class TestDecideInviteOutcomeIdempotent:
    """ACCEPTED and PENDING rows are idempotent no-ops.

    A second « invite » click must not resurrect the row nor re-send
    the email — the admin learns « already in this state »."""

    def test_accepted_is_already_accepted(self):
        row = _accepted(user_id=42, role=BWRoleType.BWMI.value)
        decision = _invite(role_assignments=[row], user_id=42)
        assert decision.action == InviteAction.NOOP
        assert decision.outcome_code == InvitationOutcomeCode.ALREADY_ACCEPTED
        assert decision.existing is row

    def test_pending_is_already_pending(self):
        row = _pending(user_id=42, role=BWRoleType.BWMI.value)
        decision = _invite(role_assignments=[row], user_id=42)
        assert decision.action == InviteAction.NOOP
        assert decision.outcome_code == InvitationOutcomeCode.ALREADY_PENDING
        assert decision.existing is row

    def test_idempotent_ignored_when_role_differs(self):
        """An ACCEPTED BWPRI row must NOT block a BWMI invitation.
        The match key is `(user_id, role_type)`, not user alone."""
        row = _accepted(user_id=42, role=BWRoleType.BWPRI.value)
        decision = _invite(
            role_assignments=[row], user_id=42, role_value=BWRoleType.BWMI.value
        )
        assert decision.action == InviteAction.CREATE_NEW

    def test_idempotent_ignored_when_user_differs(self):
        row = _accepted(user_id=99, role=BWRoleType.BWMI.value)
        decision = _invite(role_assignments=[row], user_id=42)
        assert decision.action == InviteAction.CREATE_NEW


class TestDecideInviteOutcomeResurrect:
    """REJECTED / EXPIRED rows must be resurrected, not duplicated."""

    @pytest.mark.parametrize("factory", [_rejected, _expired])
    def test_dead_status_resurrects(self, factory):
        row = factory(user_id=7, role=BWRoleType.BWMI.value)
        decision = _invite(role_assignments=[row], user_id=7)
        assert decision.action == InviteAction.RESURRECT
        assert decision.outcome_code == InvitationOutcomeCode.RESENT
        assert decision.existing is row

    def test_resurrect_picks_the_matching_row_not_a_sibling(self):
        """When several rows exist for the same user but different
        roles, the decision must return the matching one — that's
        what the shell will update."""
        other = _accepted(user_id=7, role=BWRoleType.BWPRI.value)
        target = _rejected(user_id=7, role=BWRoleType.BWMI.value)
        decision = _invite(
            role_assignments=[other, target],
            user_id=7,
            role_value=BWRoleType.BWMI.value,
        )
        assert decision.action == InviteAction.RESURRECT
        assert decision.existing is target


class TestDecideInviteOutcomeCreate:
    """No matching row → fresh PENDING assignment to be created."""

    def test_empty_assignments_creates(self):
        decision = _invite(role_assignments=[])
        assert decision.action == InviteAction.CREATE_NEW
        assert decision.outcome_code == InvitationOutcomeCode.CREATED
        assert decision.existing is None

    def test_none_assignments_creates(self):
        """`business_wall.role_assignments` is None when the BW has
        never had any assignment. The decision must tolerate it."""
        decision = _invite(role_assignments=None)
        assert decision.action == InviteAction.CREATE_NEW

    def test_unrelated_rows_create(self):
        """Rows for other users / other roles must not block."""
        decision = _invite(
            role_assignments=[
                _accepted(user_id=99, role=BWRoleType.BWMI.value),
                _pending(user_id=100, role=BWRoleType.BWPRI.value),
            ],
            user_id=1,
        )
        assert decision.action == InviteAction.CREATE_NEW


class TestDecideRevokeAction:
    """Pure: returns the matching assignment or None."""

    def test_empty_list_returns_none(self):
        assert decide_revoke_action([], 1, BWRoleType.BWMI.value) is None

    def test_none_list_returns_none(self):
        assert decide_revoke_action(None, 1, BWRoleType.BWMI.value) is None

    def test_matching_user_and_role_returned(self):
        target = _accepted(user_id=42, role=BWRoleType.BWPRI.value)
        result = decide_revoke_action(
            [_accepted(user_id=99, role=BWRoleType.BWMI.value), target],
            42,
            BWRoleType.BWPRI.value,
        )
        assert result is target

    def test_no_match_returns_none(self):
        result = decide_revoke_action(
            [_accepted(user_id=99, role=BWRoleType.BWMI.value)],
            42,
            BWRoleType.BWMI.value,
        )
        assert result is None

    def test_different_role_same_user_no_match(self):
        """The (user_id, role_type) tuple is the match key.
        A BWMI row must not be returned when revoking BWPRI."""
        result = decide_revoke_action(
            [_accepted(user_id=42, role=BWRoleType.BWMI.value)],
            42,
            BWRoleType.BWPRI.value,
        )
        assert result is None

    def test_revokable_regardless_of_invitation_status(self):
        """Even REJECTED rows should be picked up — revocation
        deletes the row outright."""
        target = _rejected(user_id=1, role=BWRoleType.BWMI.value)
        result = decide_revoke_action([target], 1, BWRoleType.BWMI.value)
        assert result is target

    def test_returns_first_match(self):
        """Two rows with the same (user, role) shouldn't exist
        (unique index), but if they do the decision is deterministic :
        the iteration-order-first row is returned."""
        first = _accepted(user_id=1)
        first.label = "first"
        second = _pending(user_id=1)
        second.label = "second"
        result = decide_revoke_action([first, second], 1, BWRoleType.BWMI.value)
        assert result is first


class TestSelectNonMemberAssignments:
    """`ensure_roles_membership`'s policy : drop every assignment
    whose user is no longer a member of the BW's organisation."""

    def test_empty_list(self):
        assert select_non_member_assignments([], {1, 2}) == []

    def test_none_list(self):
        assert select_non_member_assignments(None, {1, 2}) == []

    def test_all_members_keeps_all(self):
        rows = [_accepted(user_id=1), _accepted(user_id=2), _accepted(user_id=3)]
        assert select_non_member_assignments(rows, {1, 2, 3}) == []

    def test_no_members_drops_all(self):
        rows = [_accepted(user_id=1), _accepted(user_id=2)]
        result = select_non_member_assignments(rows, set())
        # Identity-based assertion (StubAssignment isn't hashable).
        assert len(result) == 2
        assert all(r in rows for r in result)
        assert all(r in result for r in rows)

    def test_mixed_returns_only_non_members(self):
        keep_a = _accepted(user_id=1)
        drop_a = _accepted(user_id=2)
        keep_b = _accepted(user_id=3)
        drop_b = _accepted(user_id=4)
        rows = [keep_a, drop_a, keep_b, drop_b]
        result = select_non_member_assignments(rows, {1, 3})
        # State assertion : we get exactly the to-drop rows.
        assert result == [drop_a, drop_b]
        assert keep_a not in result
        assert keep_b not in result

    def test_preserves_input_order(self):
        """Tests later assert on the returned list directly, so the
        function must keep the original iteration order so the shell
        deletes them in a deterministic sequence."""
        rows = [_accepted(user_id=i) for i in (1, 2, 3, 4)]
        result = select_non_member_assignments(rows, {2})
        assert [a.user_id for a in result] == [1, 3, 4]

    def test_role_type_irrelevant_to_pruning(self):
        """Membership pruning is per-user, not per-role. Even a
        BW_OWNER row of a non-member must be returned (the shell
        decides whether to actually delete it, but the policy here
        is « not a member → drop »)."""
        rows = [
            StubAssignment(user_id=1, role_type=BWRoleType.BW_OWNER.value),
            StubAssignment(user_id=2, role_type=BWRoleType.BWMI.value),
        ]
        result = select_non_member_assignments(rows, {2})
        assert len(result) == 1
        assert result[0].user_id == 1


class TestInviteDecisionShape:
    """Pin the dataclass contract the orchestrating shell relies on."""

    def test_decision_has_three_fields(self):
        d = InviteDecision(
            InviteAction.CREATE_NEW, InvitationOutcomeCode.CREATED, None
        )
        assert d.action == InviteAction.CREATE_NEW
        assert d.outcome_code == InvitationOutcomeCode.CREATED
        assert d.existing is None

    def test_decision_is_frozen(self):
        d = InviteDecision(InviteAction.NOOP, InvitationOutcomeCode.ALREADY_PENDING)
        with pytest.raises(Exception):
            d.action = InviteAction.FAIL  # type: ignore[misc]

    def test_invite_action_members(self):
        """Pin the four canonical actions the shell branches on."""
        assert {a.value for a in InviteAction} == {
            "create_new",
            "resurrect",
            "noop",
            "fail",
        }


# Silence the "unused" lint hint on `field` — kept around in case
# future stand-ins need default-factory attributes.
_ = field
