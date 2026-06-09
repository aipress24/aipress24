# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `InvitationOutcome` value object and the
`InvitationOutcomeCode` enum in `app.modules.bw.bw_activation.bw_invitation`.

Bug #0139 v2 (cited in the source) — the original code collapsed
every outcome into a `bool`, so the admin UI told them « invitation
sent ! » even when the invitation had been silently dropped (user
not in org, account inactive, etc.). The value-object refactor
distinguishes three families :

- **Success** : `CREATED` or `RESENT` — a PENDING role was just
  written, mail + notification dispatched.
- **Idempotent no-op** : `ALREADY_PENDING` / `ALREADY_ACCEPTED` —
  the user is already in the desired state.
- **Failure** : every `FAILED_*` code — nothing happened, the admin
  needs a message explaining why.

Pin the contract so a future refactor that drops a code or
reshuffles the families is caught at PR time. The `__bool__` dunder
matters too — every `if invite_user_role(...):` call site relies on
it returning False for « nothing happened ».
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcome,
    InvitationOutcomeCode,
)


class TestInvitationOutcomeCodeMembers:
    def test_all_canonical_codes_present(self):
        """Pin the eight canonical codes Erick spec'd. Adding a
        ninth must update this test — that's the point."""
        codes = {m.value for m in InvitationOutcomeCode}
        assert codes == {
            "created",
            "resent",
            "already_pending",
            "already_accepted",
            "failed_inactive",
            "failed_not_in_org",
            "failed_no_org",
            "failed_unknown_email",
        }

    def test_failure_codes_share_prefix(self):
        """Every failure code starts with `failed_` — pinned because
        `is_failure` relies on the prefix. A new failure code without
        the prefix would silently be misclassified."""
        for code in InvitationOutcomeCode:
            if code.name.startswith("FAILED_"):
                assert code.value.startswith("failed_"), (
                    f"{code.name} value should start with `failed_`"
                )

    def test_success_codes_dont_start_with_failed(self):
        """Defensive : success / idempotent codes must NOT start
        with `failed_` (would be misclassified by `is_failure`)."""
        non_failure = (
            InvitationOutcomeCode.CREATED,
            InvitationOutcomeCode.RESENT,
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
        )
        for code in non_failure:
            assert not code.value.startswith("failed_")


class TestInvitationOutcomeIsSuccess:
    @pytest.mark.parametrize(
        "code", [InvitationOutcomeCode.CREATED, InvitationOutcomeCode.RESENT]
    )
    def test_success_codes(self, code):
        """`CREATED` (fresh invite) and `RESENT` (re-firing a prior
        invitation) both count as success — both produced
        mail + in-app notification side-effects."""
        assert InvitationOutcome(code=code).is_success is True

    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
            InvitationOutcomeCode.FAILED_INACTIVE,
            InvitationOutcomeCode.FAILED_NOT_IN_ORG,
            InvitationOutcomeCode.FAILED_NO_ORG,
            InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL,
        ],
    )
    def test_non_success_codes(self, code):
        """Every other code is NOT success — including idempotent
        no-ops (they didn't write anything new)."""
        assert InvitationOutcome(code=code).is_success is False


class TestInvitationOutcomeIsFailure:
    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.FAILED_INACTIVE,
            InvitationOutcomeCode.FAILED_NOT_IN_ORG,
            InvitationOutcomeCode.FAILED_NO_ORG,
            InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL,
        ],
    )
    def test_failure_codes(self, code):
        assert InvitationOutcome(code=code).is_failure is True

    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.CREATED,
            InvitationOutcomeCode.RESENT,
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
        ],
    )
    def test_non_failure_codes(self, code):
        assert InvitationOutcome(code=code).is_failure is False


class TestInvitationOutcomeIsIdempotent:
    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
        ],
    )
    def test_idempotent_codes(self, code):
        """`ALREADY_PENDING` (a previous invite is still in flight)
        and `ALREADY_ACCEPTED` (user already has the role) are both
        idempotent : no side effect, no error to surface."""
        assert InvitationOutcome(code=code).is_idempotent is True

    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.CREATED,
            InvitationOutcomeCode.RESENT,
            InvitationOutcomeCode.FAILED_INACTIVE,
            InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL,
        ],
    )
    def test_non_idempotent_codes(self, code):
        assert InvitationOutcome(code=code).is_idempotent is False


class TestInvitationOutcomeFamiliesAreDisjoint:
    """The three families (success / idempotent / failure) must
    partition the codes — every code is in exactly one. Pin so a
    refactor that re-orders the check predicates can't accidentally
    let one code be « both success and failure » or « neither »."""

    @pytest.mark.parametrize("code", list(InvitationOutcomeCode))
    def test_each_code_in_exactly_one_family(self, code):
        outcome = InvitationOutcome(code=code)
        flags = [outcome.is_success, outcome.is_failure, outcome.is_idempotent]
        assert sum(flags) == 1, (
            f"Code {code!r} is in {sum(flags)} families "
            f"(success={outcome.is_success}, "
            f"failure={outcome.is_failure}, "
            f"idempotent={outcome.is_idempotent}) — must be exactly one"
        )


class TestInvitationOutcomeAdminMessage:
    """The `admin_message` property feeds the « invitation failed
    because… » UI banner. Pin the message strings — they're user-
    facing French, copy-edited by Erick."""

    def test_success_has_empty_message(self):
        """Success cases don't need an admin message — the success
        flash speaks for itself."""
        out = InvitationOutcome(code=InvitationOutcomeCode.CREATED)
        assert out.admin_message == ""

    def test_resent_has_empty_message(self):
        out = InvitationOutcome(code=InvitationOutcomeCode.RESENT)
        assert out.admin_message == ""

    def test_idempotent_has_empty_message(self):
        """Idempotent no-ops don't surface as admin messages — they
        flash a softer « already accepted » in the caller, not an
        error-style banner."""
        out = InvitationOutcome(code=InvitationOutcomeCode.ALREADY_PENDING)
        assert out.admin_message == ""

    def test_inactive_message_mentions_inactive_account(self):
        out = InvitationOutcome(code=InvitationOutcomeCode.FAILED_INACTIVE)
        assert "inactif" in out.admin_message.lower()

    def test_not_in_org_message_explains_remedy(self):
        """The « not in org » message tells the admin to add the
        user as a member first. Pin the keyword so a translation
        doesn't drop the remedy."""
        out = InvitationOutcome(code=InvitationOutcomeCode.FAILED_NOT_IN_ORG)
        msg = out.admin_message
        assert "membres" in msg.lower() or "organisation" in msg.lower()

    def test_unknown_email_message_explains_no_match(self):
        out = InvitationOutcome(code=InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL)
        assert "utilisateur" in out.admin_message.lower()

    def test_no_org_message_present(self):
        out = InvitationOutcome(code=InvitationOutcomeCode.FAILED_NO_ORG)
        assert out.admin_message


class TestInvitationOutcomeBool:
    """The `__bool__` dunder lets existing
    `if invite_user_role(...):` call sites keep working without a
    refactor. Pin the contract : truthy IFF success."""

    def test_created_is_truthy(self):
        out = InvitationOutcome(code=InvitationOutcomeCode.CREATED)
        assert bool(out) is True
        assert out  # The whole point of the dunder.

    def test_resent_is_truthy(self):
        assert bool(InvitationOutcome(code=InvitationOutcomeCode.RESENT)) is True

    def test_idempotent_is_falsy(self):
        """Pin so a future code that says « ALREADY_ACCEPTED is
        kind-of-success » doesn't accidentally trigger downstream
        side-effects in the old call sites."""
        assert (
            bool(InvitationOutcome(code=InvitationOutcomeCode.ALREADY_ACCEPTED))
            is False
        )

    def test_failure_is_falsy(self):
        assert (
            bool(InvitationOutcome(code=InvitationOutcomeCode.FAILED_INACTIVE)) is False
        )


class TestInvitationOutcomeImmutability:
    def test_is_frozen_dataclass(self):
        """`@dataclass(frozen=True)` — the value object can't be
        mutated after construction. Pin so a future refactor that
        loosens the dataclass options doesn't allow weird shared-
        state bugs."""
        out = InvitationOutcome(code=InvitationOutcomeCode.CREATED)
        with pytest.raises((AttributeError, TypeError)):
            out.code = InvitationOutcomeCode.RESENT  # type: ignore[misc]

    def test_email_defaults_to_empty(self):
        """The optional email field — pin the default so a future
        `None` default doesn't crash code that does `.email + ", "`."""
        out = InvitationOutcome(code=InvitationOutcomeCode.CREATED)
        assert out.email == ""

    def test_email_field_persisted(self):
        out = InvitationOutcome(
            code=InvitationOutcomeCode.CREATED, email="user@example.com"
        )
        assert out.email == "user@example.com"

    def test_equality_by_code_and_email(self):
        """`frozen=True` gives us value equality. Pin so a refactor
        that overrides `__eq__` doesn't accidentally break the
        equality model."""
        a = InvitationOutcome(code=InvitationOutcomeCode.CREATED, email="x@y.com")
        b = InvitationOutcome(code=InvitationOutcomeCode.CREATED, email="x@y.com")
        assert a == b
