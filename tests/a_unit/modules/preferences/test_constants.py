# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `MENU` in `app.modules.preferences.constants`.

The preferences side-bar is rendered from this list. Each entry's
`name` doubles as the « current page » indicator (the template
matches `entry.name == current_view_function_name`), and the
`endpoint` is fed into `url_for()` to build the link.

Pinning the contract catches three classes of silent regression :

1. **Typo in an endpoint** — the menu still renders but the link
   raises `BuildError` only when a user clicks it.
2. **Duplicate `name`** — two entries highlight at the same time,
   confusing the user about which page they're on.
3. **Missing canonical entry** — the « Modification du profil » /
   invitations / password rows are core to the page ; losing one
   silently is a UX regression no e2e test catches automatically.
"""

from __future__ import annotations

from app.modules.preferences.constants import MENU, MenuEntry


class TestMenuEntryShape:
    def test_each_entry_is_a_menuentry_instance(self):
        """All entries share the same NamedTuple shape. Defensive
        check against a future « dict-style » entry sneaking in."""
        for entry in MENU:
            assert isinstance(entry, MenuEntry)

    def test_every_field_is_a_non_empty_string(self):
        """The four fields are required by both the template and
        `url_for()`. Empty values would silently break either."""
        for entry in MENU:
            for field_name in ("name", "label", "icon", "endpoint"):
                value = getattr(entry, field_name)
                assert isinstance(value, str), (
                    f"MENU entry {entry.name!r} .{field_name} must be str"
                )
                assert value, (
                    f"MENU entry {entry.name!r} .{field_name} must be non-empty"
                )


class TestMenuStructuralInvariants:
    def test_menu_is_non_empty(self):
        assert len(MENU) > 0

    def test_names_are_unique(self):
        """The « current page » highlighting compares `entry.name`
        against the view function name. Two entries with the same
        `name` would both highlight simultaneously."""
        names = [e.name for e in MENU]
        assert len(names) == len(set(names)), f"Duplicate menu names: {names}"

    def test_labels_are_unique(self):
        """Two entries with the same label are surely a copy-paste
        mistake — the user can't distinguish them at a glance."""
        labels = [e.label for e in MENU]
        assert len(labels) == len(set(labels)), f"Duplicate menu labels: {labels}"


class TestMenuEndpointConventions:
    def test_local_endpoints_use_relative_prefix(self):
        """Endpoints inside the preferences blueprint start with `.` —
        relative endpoint resolution. Cross-blueprint endpoints (like
        `kyc.profile_page`) carry their full blueprint name. Pin the
        convention so a future contributor doesn't break the relative
        form."""
        for entry in MENU:
            if entry.endpoint.startswith("."):
                # Relative endpoint — must have content after the dot.
                assert len(entry.endpoint) > 1, (
                    f"MENU entry {entry.name!r} has bare '.' endpoint"
                )
            else:
                # Cross-blueprint — must contain a dot somewhere.
                assert "." in entry.endpoint, (
                    f"MENU entry {entry.name!r} endpoint "
                    f"{entry.endpoint!r} looks neither relative nor "
                    "qualified."
                )


class TestMenuCanonicalEntries:
    """Source-level cross-check : the canonical preferences pages
    Erick has shipped over time should not silently disappear from
    the menu. Add new pages by editing this list."""

    def test_profile_visibility_present(self):
        names = {e.name for e in MENU}
        assert "profile" in names

    def test_password_present(self):
        names = {e.name for e in MENU}
        assert "password" in names

    def test_invitations_present(self):
        """Critical : the org-invitation acceptance UX (touched by
        the recent security review) must remain accessible from the
        menu."""
        names = {e.name for e in MENU}
        assert "invitations" in names

    def test_profile_modification_present(self):
        """The link to the full KYC profile editor."""
        names = {e.name for e in MENU}
        assert "profile_page" in names

    def test_contact_options_present(self):
        names = {e.name for e in MENU}
        assert "contact_options" in names

    def test_invitations_uses_correct_endpoint(self):
        invitations = next(e for e in MENU if e.name == "invitations")
        assert invitations.endpoint == ".invitations"

    def test_profile_page_routes_to_kyc(self):
        """`profile_page` lives in the kyc blueprint — the menu must
        cross-reference it explicitly. Pin so a refactor that moves
        the profile editor into preferences doesn't silently break
        the existing link."""
        profile_page = next(e for e in MENU if e.name == "profile_page")
        assert profile_page.endpoint == "kyc.profile_page"
