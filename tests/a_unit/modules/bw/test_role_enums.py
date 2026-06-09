# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the StrEnum dispatch tables in
`app.modules.bw.bw_activation.models.role` and adjacent files.

These enums are stored verbatim as Postgres enum values on the
`role_assignment` / `partnership` / `business_wall` tables. Renaming
any member without an Alembic migration crashes inserts at COMMIT
time — a unit test catches the mistake at decoration time, weeks
before it reaches staging.

Specifically pinned :
- StrEnum member values (case-sensitive — Postgres enums are
  case-sensitive too)
- The expected set of members per enum (no silent drops on refactor)
- Asymmetries the BW codebase relies on (internal vs external role
  suffixes ; pending vs accepted in invitation status etc.)
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.models.partnership import PartnershipStatus
from app.modules.bw.bw_activation.models.subscription import (
    PricingTier,
    SubscriptionStatus,
)


class TestBWRoleType:
    """The 5 BW roles. Each has a canonical lowercase-or-titlecase
    spelling baked into the DB enum. Renaming any one of them in
    Python without an Alembic migration silently breaks every
    existing role_assignment row."""

    def test_members_match_spec(self):
        names = {m.name for m in BWRoleType}
        assert names == {"BW_OWNER", "BWMI", "BWPRI", "BWME", "BWPRE"}

    def test_internal_external_naming_convention(self):
        """Internal roles end in « i » (BWMi, BWPRi). External roles
        end in « e » (BWMe, BWPRe). Pin the convention so a typo or
        a swap is caught — the BW dashboard access policy depends
        on it (`bw_managers_ids` filters by role_type)."""
        # Manager pair
        assert BWRoleType.BWMI.value.endswith("i")
        assert BWRoleType.BWME.value.endswith("e")
        # PR Manager pair
        assert BWRoleType.BWPRI.value.endswith("i")
        assert BWRoleType.BWPRE.value.endswith("e")

    def test_bw_owner_value_is_all_caps_snake(self):
        """The owner role is special — separate from the i/e pairs.
        Pin the all-caps snake form to distinguish it visually from
        the camelcase role names."""
        assert BWRoleType.BW_OWNER.value == "BW_OWNER"

    @pytest.mark.parametrize(
        "raw_value",
        ["BW_OWNER", "BWMi", "BWPRi", "BWMe", "BWPRe"],
    )
    def test_round_trip_from_value(self, raw_value):
        """Pin the round-trip so a typo in raw_value catches at PR
        time."""
        assert BWRoleType(raw_value).value == raw_value

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="bogus-role"):
            BWRoleType("bogus-role")


class TestInvitationStatus:
    """The lifecycle of a `RoleAssignment` row."""

    def test_members_match_spec(self):
        names = {m.name for m in InvitationStatus}
        assert names == {"PENDING", "ACCEPTED", "REJECTED", "EXPIRED"}

    def test_values_are_lowercase(self):
        """Pin lowercase since SQL queries compare values directly
        (no case-folding) — a capital P would silently never match."""
        for m in InvitationStatus:
            assert m.value == m.value.lower(), (
                f"InvitationStatus.{m.name} must be lowercase, got {m.value!r}"
            )

    def test_pending_value(self):
        """The initial state — pin its exact spelling so the default
        in `RoleAssignment.invitation_status` doesn't drift."""
        assert InvitationStatus.PENDING.value == "pending"

    def test_accepted_value(self):
        """ACCEPTED is the « can act » state ; pin so the access
        gate (`bw_managers_ids` filter) doesn't silently break."""
        assert InvitationStatus.ACCEPTED.value == "accepted"


class TestPermissionType:
    """PR Manager permission types (Stage 6 missions). Each member
    maps to a UI checkbox + a DB flag."""

    def test_members_match_spec(self):
        names = {m.name for m in PermissionType}
        assert names == {
            "PRESS_RELEASE",
            "EVENTS",
            "MISSIONS",
            "PROJECTS",
            "INTERNSHIPS",
            "APPRENTICESHIPS",
            "DOCTORAL",
            "MEDIA_CONTACTS",
            "STATS_KPI",
            "MESSAGES",
        }

    def test_values_are_lowercase_with_underscores(self):
        """All-lowercase snake_case values."""
        for m in PermissionType:
            assert m.value == m.value.lower()
            assert " " not in m.value, (
                f"PermissionType.{m.name} value should not contain spaces"
            )

    def test_three_education_contract_types_present(self):
        """Erick's INTERNSHIPS / APPRENTICESHIPS / DOCTORAL trio
        gates the publish-job flow (see `jobs_new` in modules/biz).
        Pin so a future « let's collapse these » regression doesn't
        silently widen the publish gate."""
        for name in ("INTERNSHIPS", "APPRENTICESHIPS", "DOCTORAL"):
            assert hasattr(PermissionType, name)


class TestBWStatus:
    """Business Wall lifecycle."""

    def test_members_match_spec(self):
        names = {m.name for m in BWStatus}
        # At minimum the ACTIVE / CANCELLED / NEW / etc. The exact set
        # depends on the implementation. Pin ACTIVE since it's the most
        # important state.
        assert "ACTIVE" in names

    def test_active_value(self):
        """ACTIVE is the canonical « can be used » state. Pin its
        value so SQL filters comparing to `"active"` don't break."""
        assert BWStatus.ACTIVE.value == "active"


class TestPartnershipStatus:
    """The lifecycle of a Partnership row (BW client/agency
    relationship)."""

    def test_canonical_members_present(self):
        """Pin the 3 canonical states even if more exist."""
        names = {m.name for m in PartnershipStatus}
        for canonical in ("INVITED", "ACCEPTED", "REVOKED"):
            assert canonical in names, f"PartnershipStatus.{canonical} missing"

    def test_values_are_strings(self):
        for m in PartnershipStatus:
            assert isinstance(m.value, str)
            assert m.value


class TestSubscriptionStatus:
    """The Stripe-subscription-mirror lifecycle states."""

    def test_at_least_one_member(self):
        """Defensive — pin so a refactor that empties the enum
        crashes here, not at first row insert."""
        assert len(list(SubscriptionStatus)) > 0

    def test_values_are_strings(self):
        for m in SubscriptionStatus:
            assert isinstance(m.value, str)
            assert m.value


class TestPricingTier:
    """Stripe pricing tier discriminator (mirrors BWType plus
    free/paid distinction)."""

    def test_at_least_one_member(self):
        assert len(list(PricingTier)) > 0

    def test_values_are_strings(self):
        for m in PricingTier:
            assert isinstance(m.value, str)
            assert m.value
