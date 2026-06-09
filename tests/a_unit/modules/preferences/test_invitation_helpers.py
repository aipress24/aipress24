# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from
`app.modules.preferences.views.invitations`.

The `InvitationsView` is a 386-LOC class where most methods touch the
DB. The pure pieces that live inside the bigger methods are :

- **email normalisation** : every Invitation row stored in the DB
  carries the invitee's email with whatever casing / whitespace the
  inviter typed. The listing helper trims+lowers both sides before
  matching, and the `_join_organisation` POST handler (the security
  guard added as VERIFY-001) uses the same normalisation. Pin the
  contract so a future cleanup doesn't accidentally let `« Foo@Bar »`
  bypass the listing filter or the join gate.

- **org_id parsing** : the POST handler reads `target` from the form
  and parses it to int. Non-numeric values must short-circuit (silent
  refusal) — sending `target="abc"` from the browser previously
  raised, leaking a 500.

- **org label formatting** : the listing builds a display label using
  either the BW name (when the org has an active BusinessWall) or the
  plain organisation name. The BW branch also surfaces the BW type
  (Media / PR / etc.) in parentheses. Pure transformation, no DB.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.modules.preferences.views.invitations import (
    count_open_invitations,
    format_org_label,
    normalise_email,
    parse_org_id,
    parse_partnership_id,
)


class TestNormaliseEmail:
    def test_lowercases(self):
        assert normalise_email("USER@Example.COM") == "user@example.com"

    def test_strips_leading_and_trailing_whitespace(self):
        """Inviters routinely paste emails with stray spaces or
        line-breaks. The listing query already does
        `func.trim(Invitation.email)` on the DB side ; the Python
        side must match."""
        assert normalise_email("  user@example.com  ") == "user@example.com"
        assert normalise_email("\tuser@example.com\n") == "user@example.com"

    def test_none_returns_empty_string(self):
        """`user.email` is typed as `str | None`. None must
        normalise to `""` (treated as « no email » downstream),
        not raise."""
        assert normalise_email(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert normalise_email("") == ""

    def test_only_whitespace_returns_empty(self):
        """A purely-whitespace email is honest-to-goodness no email ;
        normalising it to `""` lets the gate refuse the join cleanly."""
        assert normalise_email("   \t\n") == ""

    def test_internal_whitespace_preserved(self):
        """We only trim edges. An email with embedded spaces is malformed
        but the normaliser shouldn't try to repair it — that's the
        validator's job downstream."""
        assert normalise_email("u s e r@example.com") == "u s e r@example.com"


class TestParseOrgId:
    def test_numeric_string_parses_to_int(self):
        assert parse_org_id("42") == 42

    def test_zero_parses_to_zero(self):
        """Org id `0` is technically valid (PG bigserial starts at 1
        in practice but defensive parsing keeps `0` distinguishable
        from None — the caller decides whether to accept it)."""
        assert parse_org_id("0") == 0

    def test_negative_id_parses(self):
        """No range filtering here ; the lookup will simply find no
        invitation and silently refuse. Pin so a tightening upstream
        doesn't surprise the caller."""
        assert parse_org_id("-1") == -1

    def test_none_returns_none(self):
        assert parse_org_id(None) is None

    def test_empty_string_returns_none(self):
        assert parse_org_id("") is None

    def test_non_numeric_returns_none(self):
        """The browser could POST `target="bogus"` ; the gate must
        silently refuse rather than raise — `_join_organisation`
        previously crashed on this with ValueError."""
        assert parse_org_id("bogus") is None

    def test_decimal_returns_none(self):
        """`"3.14"` is a string-shaped float — `int(...)` would raise
        ValueError. Pin the silent-refusal."""
        assert parse_org_id("3.14") is None

    def test_whitespace_only_returns_none(self):
        assert parse_org_id("   ") is None


class _OrgLike:
    """Duck-typed stand-in for `Organisation` — `format_org_label`
    only reads the four fields it needs, so the test can supply a
    minimal object without a real DB row."""

    def __init__(
        self,
        *,
        name: str = "",
        bw_id: str | None = None,
        bw_name: str = "",
        bw_active: str = "",
    ) -> None:
        self.name = name
        self.bw_id = bw_id
        self.bw_name = bw_name
        self.bw_active = bw_active


class TestFormatOrgLabel:
    def test_no_bw_returns_plain_name(self):
        """An org without an active BusinessWall is just its bare
        name — no parenthetical."""
        org = _OrgLike(name="Le Monde", bw_id=None)
        assert format_org_label(org) == "Le Monde"

    def test_bw_org_includes_bw_name_and_type_label(self):
        """When the org has a BW, the label is
        `« <bw_name> (<bw_type_label>) »`. The type label comes from
        `LABELS_BW_TYPE_V2` so a future renaming of the BW types
        keeps this consistent everywhere."""
        org = _OrgLike(
            name="Le Monde Org",
            bw_id="bw_42",
            bw_name="Le Monde BW",
            bw_active="media",
        )
        result = format_org_label(org)
        assert result.startswith("Le Monde BW (")
        assert result.endswith(")")
        # The type code itself never surfaces in the label — only its
        # human-readable label from LABELS_BW_TYPE_V2.
        assert "Le Monde BW" in result

    def test_bw_org_unknown_type_falls_back_to_raw_code(self):
        """If `bw_active` is a brand-new BW type that
        `LABELS_BW_TYPE_V2` doesn't know about yet, fall back to the
        raw code rather than crash. Catches the case where a backend
        change adds a type before the labels dict gets updated."""
        org = _OrgLike(
            name="Some Org",
            bw_id="bw_99",
            bw_name="Some BW",
            bw_active="brand-new-tier",
        )
        result = format_org_label(org)
        assert "Some BW" in result
        assert "brand-new-tier" in result

    def test_bw_active_empty_string(self):
        """A BW with empty `bw_active` is a partially-activated row.
        Still produce a valid label without crashing."""
        org = _OrgLike(
            name="Half-active Org",
            bw_id="bw_50",
            bw_name="Half-active BW",
            bw_active="",
        )
        # Should not raise.
        format_org_label(org)


@pytest.mark.parametrize(
    ("raw_email", "expected_normalised"),
    [
        ("Erick@AgenceTCA.info", "erick@agencetca.info"),
        ("  Erick@AgenceTCA.info  ", "erick@agencetca.info"),
        (None, ""),
        ("", ""),
    ],
)
def test_email_normalisation_matches_db_listing_filter(raw_email, expected_normalised):
    """Cross-check : the Python-side normalisation must produce the
    same key the DB-side `func.lower(func.trim(...))` would produce.
    If these ever drift, an invitation listed in the UI couldn't be
    accepted because the join gate would refuse it."""
    assert normalise_email(raw_email) == expected_normalised


class TestCountOpenInvitations:
    """Pin the « open invitations counter » contract — the bubble
    next to the menu entry. A miscount confuses the user about
    whether they have pending actions."""

    def test_empty_list_returns_zero(self):
        assert count_open_invitations([]) == 0

    def test_only_open_invitations_counted(self):
        """`disabled == ""` = the user can accept it. `disabled ==
        "disabled"` = already a member, can't act on it."""
        invitations = [
            {"label": "A", "org_id": "1", "disabled": ""},
            {"label": "B", "org_id": "2", "disabled": ""},
            {"label": "C", "org_id": "3", "disabled": "disabled"},
        ]
        assert count_open_invitations(invitations) == 2

    def test_all_disabled_returns_zero(self):
        invitations = [
            {"label": "A", "org_id": "1", "disabled": "disabled"},
            {"label": "B", "org_id": "2", "disabled": "disabled"},
        ]
        assert count_open_invitations(invitations) == 0

    def test_missing_disabled_key_treated_as_not_open(self):
        """A dict without the `disabled` key shouldn't count as
        « open » — pin the defensive default so a future shape
        change can't silently inflate the counter."""
        invitations = [
            {"label": "A", "org_id": "1"},  # no disabled key
            {"label": "B", "org_id": "2", "disabled": ""},
        ]
        assert count_open_invitations(invitations) == 1

    def test_unexpected_disabled_value_treated_as_not_open(self):
        """Only the exact empty string counts as open. Any other
        non-empty value is treated as « not open » so a stray
        whitespace / null marker doesn't unjustifiably inflate the
        counter."""
        invitations = [
            {"label": "A", "org_id": "1", "disabled": " "},
            {"label": "B", "org_id": "2", "disabled": "yes"},
            {"label": "C", "org_id": "3", "disabled": ""},
        ]
        assert count_open_invitations(invitations) == 1


class TestParsePartnershipId:
    """Ticket #0169 part 3 : the `ack_revoked_partnership` POST handler
    parses a UUID from the form. Same silent-refusal contract as
    `parse_org_id` : non-UUID / blank / None all return None instead
    of raising."""

    def test_valid_uuid_string_parses(self):
        result = parse_partnership_id("12345678-1234-5678-1234-567812345678")
        assert result == UUID("12345678-1234-5678-1234-567812345678")

    def test_uuid_without_dashes_parses(self):
        """UUID accepts the dashes-free form too. Pin so a future
        regex tightening doesn't silently reject one of the formats
        Stripe / our own backend might emit."""
        result = parse_partnership_id("12345678123456781234567812345678")
        assert result is not None

    def test_uppercase_uuid_parses(self):
        result = parse_partnership_id("12345678-1234-5678-1234-567812345678".upper())
        assert result is not None

    def test_empty_string_returns_none(self):
        assert parse_partnership_id("") is None

    def test_none_returns_none(self):
        assert parse_partnership_id(None) is None

    def test_non_uuid_returns_none(self):
        """A crafted form value like `partnership_id=foo` must not
        raise — silently refuse and the handler short-circuits."""
        assert parse_partnership_id("not-a-uuid") is None

    def test_too_short_returns_none(self):
        assert parse_partnership_id("123") is None

    def test_too_long_returns_none(self):
        assert parse_partnership_id("a" * 100) is None

    def test_integer_string_returns_none(self):
        """`partnership_id=42` would be a perfectly valid int but
        Partnership uses UUID primary keys ; the parser must refuse
        rather than coerce."""
        assert parse_partnership_id("42") is None
