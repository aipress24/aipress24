# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the email-based BW invite/revoke helpers in
`app.modules.bw.bw_activation.bw_invitation`.

The four helpers under test (`invite_bwmi_by_email`,
`revoke_bwmi_by_email`, `invite_bwpri_by_email`, `revoke_bwpri_by_email`)
form the email-facing entry-point to BW role management. The admin UI
posts a textarea of emails ; each line is funneled through one of these
helpers. Bug #0139 v2 traced silently-dropped invitations to two
collaborators that the original code reached for via module-level
imports : `get_user_per_email` (DB lookup) and `invite_user_role` /
`revoke_user_role` (transactional shell with mail + notifications).

Pattern B refactor makes the two collaborators injectable via
keyword-only `user_lookup=` and `invite_fn=` / `revoke_fn=` defaults.
The production defaults are preserved — existing callers in
`routes/stage_b4.py` keep working untouched. The tests pass plain
`def fake_lookup(email): return _User(...)` callables and a fake
`invite_fn` that returns a canned `InvitationOutcome` we assert on.

We verify TANGIBLE OUTCOMES — the returned `InvitationOutcome` and
`bool` — never « was the fake called ». No stdlib-mock idioms, no
fixture-based monkey-patching. The injected callable IS the test seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcome,
    InvitationOutcomeCode,
    invite_bwmi_by_email,
    invite_bwpri_by_email,
    revoke_bwmi_by_email,
    revoke_bwpri_by_email,
)
from app.modules.bw.bw_activation.models import BWRoleType

# --------------------------------------------------------------------------- #
# Stub collaborators                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class _FakeUser:
    """Minimal stand-in for `app.models.auth.User` — enough surface to
    exercise the active/inactive branches the helpers care about."""

    email: str = "alice@example.com"
    active: bool = True
    id: int = 1


@dataclass
class _FakeBusinessWall:
    """Marker object passed through to the injected `invite_fn` /
    `revoke_fn` unchanged. The helpers never inspect this — only the
    seams do."""

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
    """A stub `invite_fn` whose canned return value is the test
    seam. The recorder ALSO stores the role passed in so the test
    can assert the helper threaded the right `BWRoleType` through —
    that's a tangible outcome (the seam's input) not « was it called »
    behavior assertion : if the wrong role landed in DB in real life,
    the invitation row would be wrong."""

    outcome: InvitationOutcome
    received_role: BWRoleType | None = field(default=None)
    received_business_wall: _FakeBusinessWall | None = field(default=None)
    received_user: _FakeUser | None = field(default=None)

    def __call__(
        self, business_wall, user, role: BWRoleType
    ) -> InvitationOutcome:
        self.received_role = role
        self.received_business_wall = business_wall
        self.received_user = user
        return self.outcome


@dataclass
class _RevokeRecorder:
    """Counterpart for `revoke_fn`. The boolean return value is the
    seam ; we also record the role to confirm the helper picked the
    right `BWRoleType`."""

    result: bool
    received_role: BWRoleType | None = field(default=None)

    def __call__(self, business_wall, user, role: BWRoleType) -> bool:
        self.received_role = role
        return self.result


# --------------------------------------------------------------------------- #
# invite_bwmi_by_email                                                        #
# --------------------------------------------------------------------------- #


class TestInviteBwmiByEmail:
    def test_unknown_email_returns_failed_unknown(self):
        """No user matched → `FAILED_UNKNOWN_EMAIL`. Pin so the admin
        UI keeps surfacing « no such user »."""
        outcome = invite_bwmi_by_email(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
            invite_fn=_InviteRecorder(
                outcome=InvitationOutcome(InvitationOutcomeCode.CREATED)
            ),
        )
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        assert outcome.email == "ghost@example.com"
        assert bool(outcome) is False

    def test_unknown_email_preserves_input_email_in_outcome(self):
        """The `email` field of the outcome — used by the admin flash
        banner — must echo the input verbatim."""
        outcome = invite_bwmi_by_email(
            _FakeBusinessWall(),
            "Strange.Case+Tag@Example.COM",
            user_lookup=_lookup_returning(None),
        )
        assert outcome.email == "Strange.Case+Tag@Example.COM"

    def test_inactive_user_returns_failed_unknown(self):
        """An inactive account is treated as « no such user » — same
        as `None`. Pin : the admin should never accidentally invite a
        deactivated account."""
        inactive = _FakeUser(email="zombie@example.com", active=False)
        outcome = invite_bwmi_by_email(
            _FakeBusinessWall(),
            "zombie@example.com",
            user_lookup=_lookup_returning(inactive),
        )
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL

    def test_active_user_delegates_to_invite_fn(self):
        """Active user → the helper returns whatever `invite_fn`
        returns. Pin the pass-through so the helper doesn't swallow
        the rich outcome."""
        canned = InvitationOutcome(
            InvitationOutcomeCode.CREATED, email="alice@example.com"
        )
        recorder = _InviteRecorder(outcome=canned)
        outcome = invite_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=recorder,
        )
        assert outcome is canned

    def test_active_user_threads_bwmi_role(self):
        """The helper must call `invite_fn` with `BWRoleType.BWMI`.
        Bug-magnet : a copy-paste from the BWPRI helper would silently
        invite the wrong role. Pin the contract via the seam input."""
        recorder = _InviteRecorder(
            outcome=InvitationOutcome(InvitationOutcomeCode.CREATED)
        )
        invite_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=recorder,
        )
        assert recorder.received_role == BWRoleType.BWMI

    def test_active_user_threads_business_wall_and_user(self):
        """The BW + user objects must reach `invite_fn` untouched —
        a future « wrapper that picks a different user » regression
        would be silently dropped role assignments."""
        bw = _FakeBusinessWall(name="acme-bw")
        user = _FakeUser(email="alice@example.com", id=42)
        recorder = _InviteRecorder(
            outcome=InvitationOutcome(InvitationOutcomeCode.CREATED)
        )
        invite_bwmi_by_email(
            bw,
            "alice@example.com",
            user_lookup=_lookup_returning(user),
            invite_fn=recorder,
        )
        assert recorder.received_business_wall is bw
        assert recorder.received_user is user

    @pytest.mark.parametrize(
        "canned_code",
        [
            InvitationOutcomeCode.CREATED,
            InvitationOutcomeCode.RESENT,
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
            InvitationOutcomeCode.FAILED_INACTIVE,
            InvitationOutcomeCode.FAILED_NOT_IN_ORG,
            InvitationOutcomeCode.FAILED_NO_ORG,
        ],
    )
    def test_propagates_any_invite_fn_outcome(self, canned_code):
        """The helper is a pass-through for whatever the inner
        invitation pipeline produced — pin so every code Erick added
        to the value object reaches the admin UI."""
        canned = InvitationOutcome(canned_code, email="alice@example.com")
        outcome = invite_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=_InviteRecorder(outcome=canned),
        )
        assert outcome is canned


# --------------------------------------------------------------------------- #
# revoke_bwmi_by_email                                                        #
# --------------------------------------------------------------------------- #


class TestRevokeBwmiByEmail:
    def test_unknown_email_returns_false(self):
        """No matching user → revocation is a no-op returning False.
        The admin UI relies on the bool to decide whether to flash a
        success or a « nothing happened »."""
        result = revoke_bwmi_by_email(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
            revoke_fn=_RevokeRecorder(result=True),
        )
        assert result is False

    def test_inactive_user_returns_false(self):
        """Inactive account → False without calling `revoke_fn`. Pin
        so a future « let's revoke roles on deactivation too » change
        is an explicit decision, not a silent side-effect."""
        result = revoke_bwmi_by_email(
            _FakeBusinessWall(),
            "zombie@example.com",
            user_lookup=_lookup_returning(
                _FakeUser(email="zombie@example.com", active=False)
            ),
            revoke_fn=_RevokeRecorder(result=True),
        )
        assert result is False

    def test_active_user_delegates_to_revoke_fn(self):
        """The boolean returned by `revoke_fn` is propagated verbatim."""
        result = revoke_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=_RevokeRecorder(result=True),
        )
        assert result is True

    def test_active_user_no_assignment_returns_false(self):
        """`revoke_fn` returning False (no assignment found) is
        propagated. Pin so the admin doesn't get a false-positive."""
        result = revoke_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=_RevokeRecorder(result=False),
        )
        assert result is False

    def test_active_user_threads_bwmi_role(self):
        """The role threaded to `revoke_fn` must be `BWRoleType.BWMI`.
        A copy-paste regression from the BWPRI sibling would revoke
        the wrong role in real DB life."""
        recorder = _RevokeRecorder(result=True)
        revoke_bwmi_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=recorder,
        )
        assert recorder.received_role == BWRoleType.BWMI


# --------------------------------------------------------------------------- #
# invite_bwpri_by_email                                                       #
# --------------------------------------------------------------------------- #


class TestInviteBwpriByEmail:
    def test_unknown_email_returns_failed_unknown(self):
        outcome = invite_bwpri_by_email(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
        )
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        assert outcome.email == "ghost@example.com"

    def test_inactive_user_returns_failed_unknown(self):
        outcome = invite_bwpri_by_email(
            _FakeBusinessWall(),
            "zombie@example.com",
            user_lookup=_lookup_returning(
                _FakeUser(email="zombie@example.com", active=False)
            ),
        )
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL

    def test_active_user_threads_bwpri_role(self):
        """The role threaded to `invite_fn` must be `BWRoleType.BWPRI`.
        Mirror of the BWMI test — pinning both protects the cross-role
        copy-paste regression in either direction."""
        recorder = _InviteRecorder(
            outcome=InvitationOutcome(InvitationOutcomeCode.CREATED)
        )
        invite_bwpri_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=recorder,
        )
        assert recorder.received_role == BWRoleType.BWPRI

    def test_active_user_delegates_to_invite_fn(self):
        """Pass-through behaviour : pin so future « let's
        post-process the outcome here » regressions don't drop info."""
        canned = InvitationOutcome(
            InvitationOutcomeCode.RESENT, email="alice@example.com"
        )
        outcome = invite_bwpri_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=_InviteRecorder(outcome=canned),
        )
        assert outcome is canned


# --------------------------------------------------------------------------- #
# revoke_bwpri_by_email                                                       #
# --------------------------------------------------------------------------- #


class TestRevokeBwpriByEmail:
    def test_unknown_email_returns_false(self):
        result = revoke_bwpri_by_email(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
            revoke_fn=_RevokeRecorder(result=True),
        )
        assert result is False

    def test_inactive_user_still_revokes(self):
        """Subtle asymmetry with `revoke_bwmi_by_email`: the BWPRI
        sibling intentionally does NOT short-circuit on inactive — an
        inactive PR Manager still needs role cleanup. Pin the
        documented behaviour : `revoke_fn` IS called for inactive."""
        recorder = _RevokeRecorder(result=True)
        result = revoke_bwpri_by_email(
            _FakeBusinessWall(),
            "zombie@example.com",
            user_lookup=_lookup_returning(
                _FakeUser(email="zombie@example.com", active=False)
            ),
            revoke_fn=recorder,
        )
        assert result is True
        assert recorder.received_role == BWRoleType.BWPRI

    def test_active_user_threads_bwpri_role(self):
        recorder = _RevokeRecorder(result=True)
        revoke_bwpri_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=recorder,
        )
        assert recorder.received_role == BWRoleType.BWPRI

    def test_active_user_no_assignment_returns_false(self):
        result = revoke_bwpri_by_email(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=_RevokeRecorder(result=False),
        )
        assert result is False


# --------------------------------------------------------------------------- #
# Symmetry across BWMI / BWPRI                                                #
# --------------------------------------------------------------------------- #


class TestInviteSymmetryAcrossRoles:
    """The two invite helpers should be structurally identical except
    for the role threaded to `invite_fn`. Parametrize over them so a
    drift in one (e.g. swallowing the outcome, mis-handling None) is
    caught immediately."""

    @pytest.mark.parametrize(
        ("helper", "expected_role"),
        [
            (invite_bwmi_by_email, BWRoleType.BWMI),
            (invite_bwpri_by_email, BWRoleType.BWPRI),
        ],
    )
    def test_unknown_email_emits_failed_unknown(self, helper, expected_role):
        outcome = helper(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
        )
        assert outcome.code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        # The expected role is documentation — the helper never reached
        # the invite_fn so `expected_role` isn't observable here, but
        # we keep the parameter for symmetry with the success test.
        assert expected_role in (BWRoleType.BWMI, BWRoleType.BWPRI)

    @pytest.mark.parametrize(
        ("helper", "expected_role"),
        [
            (invite_bwmi_by_email, BWRoleType.BWMI),
            (invite_bwpri_by_email, BWRoleType.BWPRI),
        ],
    )
    def test_active_user_threads_correct_role(self, helper, expected_role):
        recorder = _InviteRecorder(
            outcome=InvitationOutcome(InvitationOutcomeCode.CREATED)
        )
        helper(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            invite_fn=recorder,
        )
        assert recorder.received_role == expected_role


class TestRevokeSymmetryAcrossRoles:
    @pytest.mark.parametrize(
        ("helper", "expected_role"),
        [
            (revoke_bwmi_by_email, BWRoleType.BWMI),
            (revoke_bwpri_by_email, BWRoleType.BWPRI),
        ],
    )
    def test_unknown_email_returns_false(self, helper, expected_role):
        result = helper(
            _FakeBusinessWall(),
            "ghost@example.com",
            user_lookup=_lookup_returning(None),
            revoke_fn=_RevokeRecorder(result=True),
        )
        assert result is False
        assert expected_role in (BWRoleType.BWMI, BWRoleType.BWPRI)

    @pytest.mark.parametrize(
        ("helper", "expected_role"),
        [
            (revoke_bwmi_by_email, BWRoleType.BWMI),
            (revoke_bwpri_by_email, BWRoleType.BWPRI),
        ],
    )
    def test_active_user_threads_correct_role(self, helper, expected_role):
        recorder = _RevokeRecorder(result=True)
        helper(
            _FakeBusinessWall(),
            "alice@example.com",
            user_lookup=_lookup_returning(_FakeUser()),
            revoke_fn=recorder,
        )
        assert recorder.received_role == expected_role
