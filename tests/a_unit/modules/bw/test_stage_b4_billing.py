# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-unit tests for the B4 (« Manage internal roles ») and Stripe
billing-portal routes.

Both modules used to mix Flask request glue with three pieces of
pure logic that drive the actual feature:

1. **Failure-banner formatting** — bug #0139 v2 surfaced *only*
   failed invitation outcomes as red banners; success / idempotent
   outcomes stayed silent. We pin the banner string so a future
   wording tweak that drops the failure reason (or strips the
   placeholder for empty e-mails) is caught.

2. **Role-assignment categorisation** — the B4 template needs four
   buckets (BWMi members / BWMi invitations / BWPRi members /
   BWPRi invitations) plus the owner slot. The legacy code looped
   twice and silently swallowed `NotFound` user-loads. Pin the
   bucketing, the « unknown user » skip, the owner fallback, the
   pending / accepted split — every branch the template depends on.

3. **Stripe customer-id resolution** — `_resolve_stripe_customer_id`
   reads the id from the Organisation first, falls back to the
   Subscription for pre-migration rows (cf. `specs/finances.md`
   §3). Pin the precedence — an Organisation id wins even when the
   Subscription also has one — and the `None` outcome that the
   route turns into the « no subscription » flash.

All three are now pure helpers (Pattern A + Pattern B : the
categoriser takes a `user_loader` callable). Tests construct
plain stub objects only — no mocking, no fixture-driven monkey
business, no captured-call recorders.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcome,
    InvitationOutcomeCode,
)
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.routes.billing_portal import (
    _resolve_stripe_customer_id,
)
from app.modules.bw.bw_activation.routes.stage_b4 import (
    _categorize_role_assignments,
    _format_failure_flash,
)

# ---------------------------------------------------------------------------
# Stubs: ORM-free stand-ins for User / RoleAssignment / Organisation /
# Subscription / BusinessWall.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserStub:
    """Minimal duck for `User` — only the two attributes the
    categoriser reads (`email`, `full_name`)."""

    id: int
    email: str
    full_name: str


@dataclass(frozen=True)
class AssignmentStub:
    """Minimal duck for `RoleAssignment` — `.role_type`,
    `.invitation_status`, `.user_id` are the only fields touched."""

    role_type: str
    invitation_status: str
    user_id: int


def _loader_from(users: dict[int, UserStub]):
    """Build a deterministic `user_loader` over an in-memory dict.
    Missing ids raise `NotFound` (the only branch the categoriser
    handles specially)."""

    def _load(user_id):
        if user_id not in users:
            raise NotFound
        return users[user_id]

    return _load


# ---------------------------------------------------------------------------
# _format_failure_flash — pure string formatting.
# ---------------------------------------------------------------------------


class TestFormatFailureFlash:
    """The string the admin sees when an invitation silently failed
    (bug #0139 v2). Pin the wording — copy-edited French, must
    include the e-mail and the failure reason."""

    def test_includes_email_and_admin_message(self):
        out = InvitationOutcome(
            code=InvitationOutcomeCode.FAILED_NOT_IN_ORG,
            email="alice@example.com",
        )
        msg = _format_failure_flash(out)
        assert "alice@example.com" in msg
        assert out.admin_message in msg
        assert msg.startswith("Invitation impossible pour ")

    def test_empty_email_falls_back_to_placeholder(self):
        """Admin typed only commas / whitespace — the banner must
        still render with a localized placeholder so it's never bare."""
        out = InvitationOutcome(
            code=InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL, email=""
        )
        msg = _format_failure_flash(out)
        assert "(adresse vide)" in msg
        assert out.admin_message in msg

    @pytest.mark.parametrize(
        "code",
        [
            InvitationOutcomeCode.FAILED_INACTIVE,
            InvitationOutcomeCode.FAILED_NOT_IN_ORG,
            InvitationOutcomeCode.FAILED_NO_ORG,
            InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL,
        ],
    )
    def test_every_failure_code_yields_non_empty_banner(self, code):
        """All four FAILED_* codes have a non-empty admin message,
        so the banner is never trivial. If a future refactor drops
        the message for one code, the banner would degrade to
        « Invitation impossible pour x@y.com : »."""
        out = InvitationOutcome(code=code, email="x@y.com")
        msg = _format_failure_flash(out)
        # Must contain a colon plus something after it.
        prefix, _, suffix = msg.partition(": ")
        assert prefix
        assert suffix.strip()

    def test_format_is_deterministic(self):
        """Same input twice ⇒ identical output — pin the absence of
        time / random state in the formatter."""
        out = InvitationOutcome(
            code=InvitationOutcomeCode.FAILED_INACTIVE, email="bob@c.com"
        )
        assert _format_failure_flash(out) == _format_failure_flash(out)


# ---------------------------------------------------------------------------
# _categorize_role_assignments — pure (with injected loader).
# ---------------------------------------------------------------------------


class TestCategorizeRoleAssignmentsEmpty:
    def test_none_yields_empty_buckets(self):
        """`role_assignments` may be `None` on a fresh BW — return
        all-empty rather than crashing."""
        result = _categorize_role_assignments(None, user_loader=_loader_from({}))
        assert result == {
            "owner_info": {},
            "bwmi_members": [],
            "bwmi_invitations": [],
            "bwpri_members": [],
            "bwpri_invitations": [],
        }

    def test_empty_list_yields_empty_buckets(self):
        result = _categorize_role_assignments([], user_loader=_loader_from({}))
        assert result["owner_info"] == {}
        assert result["bwmi_members"] == []


class TestCategorizeRoleAssignmentsOwner:
    """The owner slot uses its own bucket (`owner_info` dict) — the
    template renders it apart from the members table."""

    def test_owner_user_loaded_into_dict(self):
        owner = UserStub(id=1, email="owner@x.com", full_name="Alice Owner")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=1,
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({1: owner})
        )
        assert result["owner_info"] == {
            "email": "owner@x.com",
            "full_name": "Alice Owner",
        }

    def test_owner_load_failure_falls_back_to_inconnu(self):
        """`get_obj` may raise (race with delete, ghost user). The
        legacy code surfaced « Inconnu / N/A » in the template
        rather than crashing the page — pin the fallback."""
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=42,
            ),
        ]
        result = _categorize_role_assignments(assignments, user_loader=_loader_from({}))
        assert result["owner_info"] == {"email": "N/A", "full_name": "Inconnu"}

    def test_only_first_owner_wins(self):
        """Belt-and-braces : the legacy code broke after the first
        owner — pin that contract so a second BW_OWNER row (data
        corruption) doesn't silently swap the displayed owner."""
        owner1 = UserStub(id=1, email="first@x.com", full_name="First")
        owner2 = UserStub(id=2, email="second@x.com", full_name="Second")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=1,
            ),
            AssignmentStub(
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=2,
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({1: owner1, 2: owner2})
        )
        assert result["owner_info"]["email"] == "first@x.com"


class TestCategorizeRoleAssignmentsBWMi:
    """BWMi: accepted ⇒ members list ; pending / rejected /
    expired ⇒ invitations e-mail list."""

    @pytest.mark.parametrize(
        "status",
        [
            InvitationStatus.PENDING.value,
            InvitationStatus.REJECTED.value,
            InvitationStatus.EXPIRED.value,
        ],
    )
    def test_non_accepted_lands_in_invitations(self, status):
        user = UserStub(id=10, email="bwmi@x.com", full_name="BWMi User")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BWMI.value,
                invitation_status=status,
                user_id=10,
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({10: user})
        )
        assert result["bwmi_invitations"] == ["bwmi@x.com"]
        assert result["bwmi_members"] == []

    def test_accepted_lands_in_members(self):
        user = UserStub(id=10, email="bwmi@x.com", full_name="BWMi User")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=10,
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({10: user})
        )
        assert result["bwmi_members"] == [user]
        assert result["bwmi_invitations"] == []


class TestCategorizeRoleAssignmentsBWPRi:
    """BWPRi: same split as BWMi but in its own bucket."""

    def test_accepted_pri_in_members_pending_in_invitations(self):
        accepted = UserStub(id=20, email="ok@x.com", full_name="OK")
        pending = UserStub(id=21, email="wait@x.com", full_name="Wait")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=20,
            ),
            AssignmentStub(
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.PENDING.value,
                user_id=21,
            ),
        ]
        result = _categorize_role_assignments(
            assignments,
            user_loader=_loader_from({20: accepted, 21: pending}),
        )
        assert result["bwpri_members"] == [accepted]
        assert result["bwpri_invitations"] == ["wait@x.com"]
        # BWMi buckets stay empty — pin the cross-bucket isolation.
        assert result["bwmi_members"] == []
        assert result["bwmi_invitations"] == []


class TestCategorizeRoleAssignmentsSkipsUnknownUsers:
    """`get_obj` may raise `NotFound` for ghost user-ids. The legacy
    behaviour was to *skip* — never crash, never display a stub.
    Bug-class pin : a future refactor that turns `NotFound` into a
    500 would break the entire B4 page."""

    def test_notfound_user_skipped(self):
        present = UserStub(id=1, email="here@x.com", full_name="Here")
        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.PENDING.value,
                user_id=1,
            ),
            AssignmentStub(
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.PENDING.value,
                user_id=999,  # ghost
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({1: present})
        )
        assert result["bwmi_invitations"] == ["here@x.com"]

    def test_other_exception_also_skipped(self):
        """Any exception during user load is treated as « skip »
        (defensive). Pin so a future refactor that narrows the
        `except` clause doesn't unmask transient DB errors as 500."""

        msg = "transient db error"

        def angry_loader(_user_id):
            raise RuntimeError(msg)

        assignments = [
            AssignmentStub(
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.PENDING.value,
                user_id=1,
            ),
        ]
        result = _categorize_role_assignments(assignments, user_loader=angry_loader)
        # No crash, just empty buckets.
        assert result["bwmi_invitations"] == []


class TestCategorizeRoleAssignmentsUnknownRoleTypes:
    """External roles (BWME / BWPRE) are not displayed on B4. Pin
    that they're silently ignored so a future « show externals too »
    feature has to opt in explicitly."""

    @pytest.mark.parametrize(
        "external_role",
        [BWRoleType.BWME.value, BWRoleType.BWPRE.value],
    )
    def test_external_roles_silently_ignored(self, external_role):
        user = UserStub(id=1, email="ext@x.com", full_name="Ext")
        assignments = [
            AssignmentStub(
                role_type=external_role,
                invitation_status=InvitationStatus.ACCEPTED.value,
                user_id=1,
            ),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from({1: user})
        )
        # None of the four buckets contain the external user.
        assert result["bwmi_members"] == []
        assert result["bwmi_invitations"] == []
        assert result["bwpri_members"] == []
        assert result["bwpri_invitations"] == []


class TestCategorizeRoleAssignmentsMixed:
    """End-to-end pin : one assignment per family, all in a single
    call. Catches off-by-one bucketing regressions."""

    def test_mixed_population(self):
        users = {
            1: UserStub(id=1, email="owner@x.com", full_name="Owner"),
            2: UserStub(id=2, email="mi-ok@x.com", full_name="MiOK"),
            3: UserStub(id=3, email="mi-wait@x.com", full_name="MiWait"),
            4: UserStub(id=4, email="pri-ok@x.com", full_name="PriOK"),
            5: UserStub(id=5, email="pri-wait@x.com", full_name="PriWait"),
        }
        assignments = [
            AssignmentStub(BWRoleType.BW_OWNER.value, "accepted", 1),
            AssignmentStub(BWRoleType.BWMI.value, "accepted", 2),
            AssignmentStub(BWRoleType.BWMI.value, "pending", 3),
            AssignmentStub(BWRoleType.BWPRI.value, "accepted", 4),
            AssignmentStub(BWRoleType.BWPRI.value, "pending", 5),
        ]
        result = _categorize_role_assignments(
            assignments, user_loader=_loader_from(users)
        )
        assert result["owner_info"]["email"] == "owner@x.com"
        assert [u.email for u in result["bwmi_members"]] == ["mi-ok@x.com"]
        assert result["bwmi_invitations"] == ["mi-wait@x.com"]
        assert [u.email for u in result["bwpri_members"]] == ["pri-ok@x.com"]
        assert result["bwpri_invitations"] == ["pri-wait@x.com"]


# ---------------------------------------------------------------------------
# _resolve_stripe_customer_id — pure helper from billing_portal.py.
# ---------------------------------------------------------------------------


def _make_bw(*, org_customer=None, sub_customer=None, has_org=True, has_sub=True):
    """Build a minimal `BusinessWall` duck.

    The helper reads `bw.get_organisation()` and `bw.subscription`.
    Use `None` for either to simulate « no org » / « no sub ».
    """
    org = SimpleNamespace(stripe_customer_id=org_customer) if has_org else None
    sub = SimpleNamespace(stripe_customer_id=sub_customer) if has_sub else None
    return SimpleNamespace(get_organisation=lambda: org, subscription=sub)


class TestResolveStripeCustomerId:
    """`_resolve_stripe_customer_id` reads the id from the
    Organisation first, falls back to the Subscription for
    pre-migration rows. Pin the precedence rules — getting these
    wrong silently sends managers to the wrong Stripe portal."""

    def test_returns_org_id_when_org_has_one(self):
        bw = _make_bw(org_customer="cus_org_42")
        assert _resolve_stripe_customer_id(bw) == "cus_org_42"

    def test_org_id_wins_over_subscription(self):
        """Precedence is the whole point of this helper — pin it
        explicitly so a future refactor that swaps the branches
        doesn't silently break finance reporting."""
        bw = _make_bw(org_customer="cus_org_42", sub_customer="cus_sub_99")
        assert _resolve_stripe_customer_id(bw) == "cus_org_42"

    def test_falls_back_to_subscription_when_org_id_empty(self):
        bw = _make_bw(org_customer=None, sub_customer="cus_sub_99")
        assert _resolve_stripe_customer_id(bw) == "cus_sub_99"

    def test_falls_back_to_subscription_when_org_id_empty_string(self):
        """Empty string is falsy — pin that we treat it as « no id »
        not as a valid customer id (Stripe would 404)."""
        bw = _make_bw(org_customer="", sub_customer="cus_sub_99")
        assert _resolve_stripe_customer_id(bw) == "cus_sub_99"

    def test_returns_none_when_no_org_no_sub(self):
        bw = _make_bw(has_org=False, has_sub=False)
        assert _resolve_stripe_customer_id(bw) is None

    def test_returns_none_when_org_none_and_sub_id_empty(self):
        bw = _make_bw(has_org=False, sub_customer=None)
        assert _resolve_stripe_customer_id(bw) is None

    def test_returns_none_when_both_have_empty_ids(self):
        """The route turns `None` into a « no subscription » flash.
        Pin that empty strings on both sides also yield `None`."""
        bw = _make_bw(org_customer="", sub_customer="")
        assert _resolve_stripe_customer_id(bw) is None

    def test_org_none_but_sub_present(self):
        bw = _make_bw(has_org=False, sub_customer="cus_only_sub")
        assert _resolve_stripe_customer_id(bw) == "cus_only_sub"

    def test_sub_none_but_org_present(self):
        bw = _make_bw(org_customer="cus_only_org", has_sub=False)
        assert _resolve_stripe_customer_id(bw) == "cus_only_org"
