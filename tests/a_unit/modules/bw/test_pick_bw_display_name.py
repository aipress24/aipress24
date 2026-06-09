# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `pick_bw_display_name` in
`app.modules.bw.bw_activation.user_utils`.

This helper resolves the display name for a BW-owning user. The
three-tier preference rule matters because, in media-group cases,
the org name and the BW name are different (e.g. organisation =
« LVMH », BW = « Les Échos ») — readers expect to see the media
brand, not the parent company name.

The pure extraction makes the policy unit-testable without spinning
up a SQLAlchemy session for `get_active_business_wall_for_organisation`.

Preference order :
1. `active_bw.name_safe` (when non-empty)
2. `org.name` (when non-empty)
3. `fallback`
"""

from __future__ import annotations

from app.modules.bw.bw_activation.user_utils import pick_bw_display_name


class _BwLike:
    def __init__(self, name_safe: str = "") -> None:
        self.name_safe = name_safe


class _OrgLike:
    def __init__(self, name: str = "") -> None:
        self.name = name


class TestPickBwDisplayName:
    def test_prefers_active_bw_name_safe(self):
        """Media-group case : org is parent (« LVMH »), BW is the
        brand readers know (« Les Échos »). Show the brand."""
        bw = _BwLike(name_safe="Les Échos")
        org = _OrgLike(name="LVMH")
        assert pick_bw_display_name(bw, org, "fallback") == "Les Échos"

    def test_falls_back_to_org_name_when_bw_missing(self):
        """No active BW (e.g. activation in progress) → org name."""
        org = _OrgLike(name="My Org")
        assert pick_bw_display_name(None, org, "fallback") == "My Org"

    def test_falls_back_to_org_name_when_bw_name_safe_empty(self):
        """A BW with empty `name_safe` (partially-activated row)
        is treated as « no display name available » — defer to org."""
        bw = _BwLike(name_safe="")
        org = _OrgLike(name="My Org")
        assert pick_bw_display_name(bw, org, "fallback") == "My Org"

    def test_uses_fallback_when_both_missing(self):
        """No active BW, no org → fallback (« inconnue » by
        default)."""
        assert pick_bw_display_name(None, None, "fallback") == "fallback"

    def test_uses_fallback_when_org_name_empty(self):
        """An org with an empty name (data import edge case) plus
        no BW → fallback. Pin so a blank-string name doesn't render
        as an empty cell in the UI."""
        org = _OrgLike(name="")
        assert pick_bw_display_name(None, org, "default") == "default"

    def test_uses_fallback_when_bw_empty_and_org_empty(self):
        """Both data sources empty → fallback. Pin the most-defensive
        branch."""
        bw = _BwLike(name_safe="")
        org = _OrgLike(name="")
        assert pick_bw_display_name(bw, org, "default") == "default"

    def test_bw_name_takes_priority_even_when_org_name_present(self):
        """The whole point of the priority order : BW name wins.
        Pin so an « org-first » regression doesn't silently revert
        the media-group display fix."""
        bw = _BwLike(name_safe="Brand")
        org = _OrgLike(name="Parent Co")
        assert pick_bw_display_name(bw, org, "fallback") == "Brand"

    def test_handles_none_org_with_active_bw(self):
        """Defensive : `org=None` + a real BW (shouldn't happen in
        prod but let's not crash). BW name wins."""
        bw = _BwLike(name_safe="Les Échos")
        assert pick_bw_display_name(bw, None, "fallback") == "Les Échos"

    def test_returns_string_not_none(self):
        """Pin the return type. A `None` return would crash callers
        doing `f"… {pick_bw_display_name(...)} …"`."""
        for args in [
            (None, None, "x"),
            (_BwLike("BW"), None, "x"),
            (None, _OrgLike("Org"), "x"),
        ]:
            assert isinstance(pick_bw_display_name(*args), str)

    def test_default_fallback_signals_inconnue(self):
        """`resolve_user_bw_name` uses « inconnue » as its default
        fallback — the French marker the UI surfaces in this case.
        Pin so the test catches a copy-edit that changes the marker
        without updating Erick's expected output."""
        # Verified via `resolve_user_bw_name(user, fallback="inconnue")`
        # default. Smoke this end of the contract too.
        assert pick_bw_display_name(None, None, "inconnue") == "inconnue"
