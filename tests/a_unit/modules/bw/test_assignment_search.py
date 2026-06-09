# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `find_existing_assignment` and
`classify_existing_assignment` in
`app.modules.bw.bw_activation.bw_invitation`.

Both helpers are extracted from the larger `invite_user_role`
function. Their job :

- `find_existing_assignment(role_assignments, user_id, role_value)` :
  pure search through a BW's already-loaded `role_assignments` for
  an entry matching a (user, role) pair. Returns the row or None.

- `classify_existing_assignment(assignment)` : map an already-existing
  row's `invitation_status` to the outcome code we should surface :
  ACCEPTED → ALREADY_ACCEPTED, PENDING → ALREADY_PENDING, anything
  else (REJECTED / EXPIRED / null) → None (caller re-invites).

Pin both so a refactor that loosens the matching (e.g. matches by
user_id alone, ignoring role) doesn't silently let an admin
double-invite a user to a role they already hold.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcomeCode,
    classify_existing_assignment,
    find_existing_assignment,
)
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus


class _Assignment:
    """Stand-in for a `RoleAssignment` row — only the 3 fields the
    search/classify helpers touch."""

    def __init__(
        self,
        *,
        user_id: int,
        role_type: str,
        invitation_status: str = InvitationStatus.PENDING.value,
    ) -> None:
        self.user_id = user_id
        self.role_type = role_type
        self.invitation_status = invitation_status


# ── find_existing_assignment ─────────────────────────────────────────


class TestFindExistingAssignment:
    def test_empty_list_returns_none(self):
        """No assignments at all (fresh BW) → None. Pin so a future
        « assume non-empty » regression doesn't crash with IndexError."""
        assert find_existing_assignment([], user_id=42, role_value="BWMi") is None

    def test_none_role_assignments_returns_none(self):
        """SQLAlchemy can hand us `None` instead of `[]` on
        unfetched relationships. The helper must handle this
        defensively — pin so it doesn't crash with TypeError."""
        assert find_existing_assignment(None, user_id=42, role_value="BWMi") is None

    def test_finds_matching_user_and_role(self):
        ra = _Assignment(user_id=42, role_type="BWMi")
        assignments = [ra]
        result = find_existing_assignment(assignments, user_id=42, role_value="BWMi")
        assert result is ra

    def test_returns_first_match(self):
        """If the DB somehow holds two rows for the same (user, role)
        — shouldn't happen but defensive — return the first. Pin so
        a future refactor doesn't accidentally start returning the
        most-recent (which would silently change the semantics)."""
        ra1 = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        ra2 = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.PENDING.value,
        )
        result = find_existing_assignment([ra1, ra2], user_id=42, role_value="BWMi")
        assert result is ra1

    def test_no_match_returns_none(self):
        """Different user, same role : no match."""
        ra = _Assignment(user_id=99, role_type="BWMi")
        assert find_existing_assignment([ra], user_id=42, role_value="BWMi") is None

    def test_different_role_no_match(self):
        """Same user, different role : no match. Pin the « must
        match BOTH » semantics — a user holding BWMI can still be
        invited to BWPRI."""
        ra = _Assignment(user_id=42, role_type=BWRoleType.BWMI.value)
        assert (
            find_existing_assignment(
                [ra], user_id=42, role_value=BWRoleType.BWPRI.value
            )
            is None
        )

    def test_skips_non_matching_iterates_to_match(self):
        """Multiple unrelated assignments in front of the matching
        one : the iterator finds it. Pin so an « early break on
        first user_id match » regression doesn't silently miss."""
        other = _Assignment(user_id=99, role_type="BWMi")
        target = _Assignment(user_id=42, role_type="BWMi")
        result = find_existing_assignment(
            [other, target], user_id=42, role_value="BWMi"
        )
        assert result is target

    def test_role_value_comparison_is_case_sensitive(self):
        """The role_type column stores the canonical mixed-case
        spelling (« BWMi »). A lower or upper variant must not
        match — pin so a case-insensitive regression doesn't widen
        the search."""
        ra = _Assignment(user_id=42, role_type="BWMi")
        assert find_existing_assignment([ra], user_id=42, role_value="bwmi") is None
        assert find_existing_assignment([ra], user_id=42, role_value="BWMI") is None


# ── classify_existing_assignment ─────────────────────────────────────


class TestClassifyExistingAssignment:
    def test_accepted_maps_to_already_accepted(self):
        ra = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        assert classify_existing_assignment(ra) == (
            InvitationOutcomeCode.ALREADY_ACCEPTED
        )

    def test_pending_maps_to_already_pending(self):
        ra = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.PENDING.value,
        )
        assert classify_existing_assignment(ra) == (
            InvitationOutcomeCode.ALREADY_PENDING
        )

    def test_rejected_returns_none(self):
        """REJECTED → None : the caller should resurrect the row
        (re-invite). Pin so a future « also short-circuit on
        REJECTED » change is caught — the resurrection flow is
        precisely how an admin re-invites a previously-rejected
        user."""
        ra = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.REJECTED.value,
        )
        assert classify_existing_assignment(ra) is None

    def test_unknown_status_returns_none(self):
        """A status string we don't recognise (data import edge case,
        new enum member not yet handled) defaults to None →
        resurrection. Pin the conservative behaviour."""
        ra = _Assignment(
            user_id=42, role_type="BWMi", invitation_status="strange-status"
        )
        assert classify_existing_assignment(ra) is None

    def test_empty_status_returns_none(self):
        ra = _Assignment(user_id=42, role_type="BWMi", invitation_status="")
        assert classify_existing_assignment(ra) is None


class TestSearchAndClassifyChain:
    """Compose the two helpers : find then classify. This is exactly
    the call pattern inside `invite_user_role` — pinning that the
    chain works end-to-end catches regressions in the integration
    contract."""

    def test_found_accepted_yields_already_accepted(self):
        ra = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        found = find_existing_assignment([ra], user_id=42, role_value="BWMi")
        assert found is not None
        assert classify_existing_assignment(found) == (
            InvitationOutcomeCode.ALREADY_ACCEPTED
        )

    def test_found_rejected_yields_none_for_resurrection(self):
        """End-to-end : found row, REJECTED status → classify returns
        None → caller should resurrect. This is the « re-invite a
        previously rejected user » path, important to keep working."""
        ra = _Assignment(
            user_id=42,
            role_type="BWMi",
            invitation_status=InvitationStatus.REJECTED.value,
        )
        found = find_existing_assignment([ra], user_id=42, role_value="BWMi")
        assert found is not None
        assert classify_existing_assignment(found) is None

    def test_not_found_yields_none_for_fresh_invite(self):
        """No matching row → fresh invite path. Pin so the « fresh
        invite » short-circuit doesn't accidentally start checking
        unrelated rows."""
        ra = _Assignment(user_id=99, role_type="BWMi")
        found = find_existing_assignment([ra], user_id=42, role_value="BWMi")
        assert found is None
