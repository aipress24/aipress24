# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the row-to-dict transformations extracted from
`InvitationsView` in `app.modules.preferences.views.invitations`.

Each of the 4 listing methods on the view (`_role_invitations`,
`_accepted_role_invitations`, `_partnership_invitations`,
`_revoked_partnerships`) ends with a list comprehension that maps a
SQLAlchemy query row to the dict shape the Jinja template consumes.
The map itself is pure : no DB, no Flask, no g.user. Extracting it
makes the contract testable in milliseconds instead of through an
HTTP round-trip.

Pinning matters because the template fields are identifiers — change
one key without a corresponding template edit and the page renders
blank cells silently (Jinja autoescape doesn't crash on missing keys).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.preferences.views.invitations import (
    accepted_role_to_dict,
    partnership_invitation_to_dict,
    resolve_client_name,
    revoked_partnership_to_dict,
    role_invitation_to_dict,
)


class _RoleAssignment:
    """Stand-in for the `RoleAssignment` ORM row. Only the attributes
    the dict-builder reads need to exist."""

    def __init__(
        self,
        *,
        id_value: str = "ra_42",
        role_type: str = "BWPRi",
        user_id: int = 100,
        invited_at: datetime | None = None,
        accepted_at: datetime | None = None,
    ) -> None:
        self.id = id_value
        self.role_type = role_type
        self.user_id = user_id
        self.invited_at = invited_at
        self.accepted_at = accepted_at


class _BusinessWall:
    def __init__(
        self,
        *,
        id_value: str = "bw_99",
        name_safe: str = "Le Monde BW",
    ) -> None:
        self.id = id_value
        self.name_safe = name_safe


class _Partnership:
    def __init__(
        self,
        *,
        id_value: str = "p_55",
        invited_at: datetime | None = None,
        revoked_at: datetime | None = None,
    ) -> None:
        self.id = id_value
        self.invited_at = invited_at
        self.revoked_at = revoked_at


class _Organisation:
    def __init__(self, name: str) -> None:
        self.name = name


# ── role_invitation_to_dict ──────────────────────────────────────────


class TestRoleInvitationToDict:
    def test_maps_required_keys(self):
        ra = _RoleAssignment(
            id_value="ra_1",
            role_type="BWPRi",
            user_id=42,
            invited_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        bw = _BusinessWall(id_value="bw_1", name_safe="Big Media")
        out = role_invitation_to_dict(ra, bw)
        assert out["id"] == "ra_1"
        assert out["bw_id"] == "bw_1"
        assert out["bw_name"] == "Big Media"
        assert out["role_type"] == "BWPRi"
        assert out["user_id"] == 42
        assert out["invited_at"] == datetime(2026, 6, 9, tzinfo=UTC)

    def test_role_label_uses_bw_role_type_label(self):
        """`role_label` is looked up in `BW_ROLE_TYPE_LABEL` — falls
        back to the raw code when the label dict doesn't know the
        type. Pin the fallback so a freshly-added BW role doesn't
        render blank."""
        ra = _RoleAssignment(role_type="brand-new-role-2027")
        bw = _BusinessWall()
        out = role_invitation_to_dict(ra, bw)
        # Unknown role → label === raw code, never empty.
        assert out["role_label"] == "brand-new-role-2027"

    def test_empty_bw_name_safe_falls_back_to_marker(self):
        """`bw.name_safe` can be empty on partially-activated rows.
        The dict-builder substitutes a marker so the UI doesn't
        render a blank bw column."""
        ra = _RoleAssignment()
        bw = _BusinessWall(name_safe="")
        out = role_invitation_to_dict(ra, bw)
        assert out["bw_name"] == "(Nom inconnu)"

    def test_id_coerced_to_string(self):
        """The template renders `{{ row.id }}` straight into hx-vals
        attributes ; SQLA gives us the id as int or UUID, the dict
        emits str so the rendered HTML is consistent."""
        ra = _RoleAssignment(id_value=42)  # numeric
        bw = _BusinessWall(id_value=99)  # numeric
        out = role_invitation_to_dict(ra, bw)
        assert out["id"] == "42"
        assert out["bw_id"] == "99"


# ── accepted_role_to_dict ────────────────────────────────────────────


class TestAcceptedRoleToDict:
    def test_uses_accepted_at_not_invited_at(self):
        """The « accepted roles » section displays when the user
        accepted, not when they were invited. Pin the field name so
        the template's `{{ row.accepted_at }}` doesn't render blank."""
        ra = _RoleAssignment(
            invited_at=datetime(2026, 1, 1, tzinfo=UTC),
            accepted_at=datetime(2026, 1, 5, tzinfo=UTC),
        )
        bw = _BusinessWall()
        out = accepted_role_to_dict(ra, bw)
        assert "accepted_at" in out
        assert out["accepted_at"] == datetime(2026, 1, 5, tzinfo=UTC)
        # And importantly NOT the invited_at — would silently surface
        # the wrong date in the UI otherwise.
        assert "invited_at" not in out

    def test_omits_user_id(self):
        """`user_id` is on the role_invitation dict but not the
        accepted one (the row IS the user's own, displaying their own
        id is redundant). Pin the asymmetry."""
        ra = _RoleAssignment(user_id=100)
        bw = _BusinessWall()
        out = accepted_role_to_dict(ra, bw)
        assert "user_id" not in out


# ── partnership_invitation_to_dict ───────────────────────────────────


class TestPartnershipInvitationToDict:
    def test_hardcoded_role_label(self):
        """Every Partnership invitation maps to the same external
        role (« PR Manager (external) »). Pin the literal so a future
        refactor doesn't silently rename it."""
        p = _Partnership(id_value="p_1", invited_at=datetime(2026, 6, 9, tzinfo=UTC))
        bw = _BusinessWall()
        out = partnership_invitation_to_dict(p, bw)
        assert out["role_label"] == "PR Manager (external)"

    def test_maps_partnership_id_to_string(self):
        p = _Partnership(id_value=55)  # numeric
        bw = _BusinessWall()
        out = partnership_invitation_to_dict(p, bw)
        assert out["id"] == "55"

    def test_propagates_bw_name_fallback(self):
        p = _Partnership()
        bw = _BusinessWall(name_safe=None)  # missing/None
        out = partnership_invitation_to_dict(p, bw)
        assert out["bw_name"] == "(Nom inconnu)"


# ── resolve_client_name ──────────────────────────────────────────────


class TestResolveClientName:
    """Picks the display name for the client side of a partnership.
    Three-tier preference : live Organisation.name > BW.name_safe >
    marker string."""

    def test_prefers_organisation_name(self):
        bw = _BusinessWall(name_safe="BW name")
        org = _Organisation(name="Real Org")
        assert resolve_client_name(bw, org) == "Real Org"

    def test_falls_back_to_bw_name_safe_when_org_missing(self):
        bw = _BusinessWall(name_safe="BW name")
        assert resolve_client_name(bw, None) == "BW name"

    def test_falls_back_to_marker_when_both_missing(self):
        bw = _BusinessWall(name_safe="")
        assert resolve_client_name(bw, None) == "(client inconnu)"

    def test_org_takes_priority_even_with_bw_name_present(self):
        """The live Organisation is the source of truth ; the BW
        `name_safe` is only the snapshot. Pin that we don't
        accidentally invert the precedence."""
        bw = _BusinessWall(name_safe="Old Snapshot")
        org = _Organisation(name="Current Name")
        assert resolve_client_name(bw, org) == "Current Name"


# ── revoked_partnership_to_dict ──────────────────────────────────────


class TestRevokedPartnershipToDict:
    def test_maps_required_keys(self):
        p = _Partnership(
            id_value="p_1",
            revoked_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        bw = _BusinessWall(name_safe="Big Media")
        org = _Organisation(name="Big Media SA")
        out = revoked_partnership_to_dict(p, bw, org)
        assert out["id"] == "p_1"
        assert out["bw_name"] == "Big Media"
        assert out["client_name"] == "Big Media SA"
        assert out["revoked_at"] == datetime(2026, 6, 9, tzinfo=UTC)

    def test_uses_resolve_client_name_for_client_name(self):
        """The `client_name` field is delegated to `resolve_client_name`.
        Cross-check by passing an explicit None for the org and
        verifying the fallback chain still produces the right value."""
        p = _Partnership()
        bw = _BusinessWall(name_safe="Fallback BW")
        out = revoked_partnership_to_dict(p, bw, None)
        assert out["client_name"] == "Fallback BW"

    def test_omits_bw_id(self):
        """The revoked-partnerships row only shows BW name + client
        name + revoked date — no actionable links, no bw_id needed
        (no `Ack` button targets by bw_id). Pin the omission so a
        refactor doesn't accidentally add it back."""
        p = _Partnership()
        bw = _BusinessWall()
        org = _Organisation(name="Org")
        out = revoked_partnership_to_dict(p, bw, org)
        assert "bw_id" not in out
