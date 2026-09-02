# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `invite_role_by_email` in `bw_invitation`.

The email-facing entry point to BW role management: the admin UI posts a
textarea of addresses and every line is funnelled through here. Bug
#0139 v2 traced silently-dropped invitations to two collaborators the
original code reached for through module-level imports —
`get_user_per_email` (DB lookup) and `invite_user_role` (transactional
shell with mail + notifications). Both are injectable via the
keyword-only `user_lookup=` / `invite_fn=` seams; production callers use
the defaults untouched.

There used to be four helpers here — `invite_bwmi_by_email`,
`invite_bwpri_by_email` and two `revoke_*` twins — identical but for the
`BWRoleType` constant on their last line, and the revoke pair had no
production caller at all. One parameterised function replaced them, so
this file is one parameterised suite.

We verify TANGIBLE OUTCOMES — the returned `InvitationOutcome`, and the
role that reached the seam — never « was the fake called ». No
stdlib-mock idioms, no fixture-based monkey-patching. The injected
callable IS the test seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcome,
    InvitationOutcomeCode,
    invite_role_by_email,
)
from app.modules.bw.bw_activation.models import BWRoleType

#: The roles the admin UI can invite to by address.
INVITABLE_ROLES = [BWRoleType.BWMI, BWRoleType.BWPRI]


@dataclass
class _FakeUser:
    """Minimal stand-in for `app.models.auth.User` — enough surface to
    exercise the active/inactive branches the helper cares about."""

    email: str = "alice@example.com"
    active: bool = True
    id: int = 1


@dataclass
class _FakeBusinessWall:
    """Marker object passed through to the injected `invite_fn`
    unchanged. The helper never inspects it — only the seam does."""

    name: str = "BW-test"


def _lookup_returning(user: _FakeUser | None):
    """Build a `user_lookup` stub that ignores the email and returns
    the canned value. Tests assert on the outcome, not on whether the
    stub was called."""

    def _stub(_email: str) -> _FakeUser | None:
        return user

    return _stub


@dataclass
class _InviteRecorder:
    """A stub `invite_fn` whose canned return value is the test seam.

    It ALSO stores what was passed in, so a test can assert the helper
    threaded the right `BWRoleType` through — that is a tangible
    outcome (the seam's input), not a « was it called » assertion: the
    wrong role here is the wrong invitation row in production.
    """

    outcome: InvitationOutcome
    received_role: BWRoleType | None = field(default=None)
    received_business_wall: _FakeBusinessWall | None = field(default=None)
    received_user: _FakeUser | None = field(default=None)

    def __call__(self, business_wall, user, role: BWRoleType) -> InvitationOutcome:
        self.received_role = role
        self.received_business_wall = business_wall
        self.received_user = user
        return self.outcome


def _invite(user: _FakeUser | None, role: BWRoleType, recorder: _InviteRecorder | None):
    """Run the helper against canned collaborators."""
    return invite_role_by_email(
        _FakeBusinessWall(),
        "alice@example.com",
        role,
        user_lookup=_lookup_returning(user),
        invite_fn=recorder,
    )


@pytest.mark.parametrize("role", INVITABLE_ROLES)
class TestNoUsableUser:
    """No active account behind the address → nothing happens.

    The seam is passed as `None` deliberately: were the helper to invite
    anyway, the call would raise rather than quietly succeed.
    """

    def test_unknown_email_fails_with_the_reason(self, role):
        outcome = _invite(None, role, None)
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        assert outcome.is_failure
        assert not outcome

    def test_the_address_survives_into_the_outcome(self, role):
        """The admin flash names the address that failed."""
        outcome = _invite(None, role, None)
        assert outcome.email == "alice@example.com"

    def test_an_inactive_account_fails_the_same_way(self, role):
        """A deactivated account is as good as no account here."""
        outcome = _invite(_FakeUser(active=False), role, None)
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL


@pytest.mark.parametrize("role", INVITABLE_ROLES)
class TestActiveUser:
    """An active account reaches `invite_user_role` with the right role."""

    def test_the_requested_role_reaches_the_seam(self, role):
        """The regression that matters: BWMi must not invite a BWPRi.

        The role used to be baked into the helper's own name, and
        `_apply_email_list` passed it a *second* time as a separate
        argument — nothing checked the two agreed.
        """
        recorder = _InviteRecorder(InvitationOutcome(InvitationOutcomeCode.CREATED))
        _invite(_FakeUser(), role, recorder)
        assert recorder.received_role == role

    def test_the_bw_and_user_reach_the_seam_unchanged(self, role):
        recorder = _InviteRecorder(InvitationOutcome(InvitationOutcomeCode.CREATED))
        bw = _FakeBusinessWall(name="BW-42")
        user = _FakeUser(id=7)
        outcome = invite_role_by_email(
            bw,
            "alice@example.com",
            role,
            user_lookup=_lookup_returning(user),
            invite_fn=recorder,
        )
        assert recorder.received_business_wall is bw
        assert recorder.received_user is user
        assert outcome.code == InvitationOutcomeCode.CREATED

    @pytest.mark.parametrize("canned_code", list(InvitationOutcomeCode))
    def test_every_outcome_propagates_untouched(self, role, canned_code):
        """The helper decides nothing about an account it did find."""
        recorder = _InviteRecorder(InvitationOutcome(canned_code, "bob@example.com"))
        outcome = _invite(_FakeUser(), role, recorder)
        assert outcome.code == canned_code
        assert outcome.email == "bob@example.com"
