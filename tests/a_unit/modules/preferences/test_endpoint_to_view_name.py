# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `endpoint_to_view_name` in
`app.modules.preferences.menu`.

The context processor reads `request.endpoint` (which is
`"preferences.profile"` or just `"profile"` depending on the
blueprint shape, or None on routing errors) and feeds the bare
view name to `make_menu(name)` so the « current page » highlight
matches `MenuEntry.name`.

A wrong parse silently breaks the highlight — every page would
look like it's the « first » one. Pin the contract."""

from __future__ import annotations

from app.modules.preferences.constants import MENU
from app.modules.preferences.menu import endpoint_to_view_name


class TestEndpointToViewName:
    def test_blueprint_qualified_endpoint(self):
        """Standard Flask blueprint endpoint : `"blueprint.view"` →
        strips the prefix."""
        assert endpoint_to_view_name("preferences.profile") == "profile"

    def test_bare_endpoint(self):
        """Some endpoints are not behind a blueprint and come through
        as just the view name. Pass them through unchanged."""
        assert endpoint_to_view_name("profile") == "profile"

    def test_none_returns_empty_string(self):
        """A 404 / routing failure can give us `request.endpoint=None`.
        We want a falsy string so the « current » match is False
        across the board (no entry highlights)."""
        assert endpoint_to_view_name(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert endpoint_to_view_name("") == ""

    def test_double_dotted_endpoint_uses_last_segment(self):
        """A future nested-blueprint design could give us
        `"app.preferences.profile"`. Last-segment-wins is the safest
        rule. Pin so a future split-from-the-left regression doesn't
        accidentally return `"profile"` to the menu as
        `"preferences.profile"`."""
        assert endpoint_to_view_name("app.preferences.profile") == "profile"

    def test_handles_underscore_view_names(self):
        """View names like `contact_options` (with underscores) must
        be passed through unchanged."""
        assert endpoint_to_view_name("preferences.contact_options") == "contact_options"

    def test_kyc_cross_blueprint_endpoint(self):
        """The « Modification du profil » MenuEntry routes to
        `kyc.profile_page` — when the user IS on that page, we want
        the menu to highlight it as current. Pin the cross-blueprint
        match path."""
        assert endpoint_to_view_name("kyc.profile_page") == "profile_page"

    def test_security_cross_blueprint_endpoint(self):
        """The password / email entries redirect to flask-security
        endpoints. When the redirect-target page is current,
        `endpoint_to_view_name("security.change_password")` =
        `"change_password"`, which doesn't match any MenuEntry — by
        design, the redirect-source pages are the canonical ones."""
        assert endpoint_to_view_name("security.change_password") == "change_password"

    def test_no_match_with_menu_entries_for_security_redirect(self):
        """Sanity : the change_password endpoint doesn't accidentally
        match any MenuEntry.name. Pin so a future MenuEntry called
        `change_password` doesn't silently double-highlight."""
        name = endpoint_to_view_name("security.change_password")
        menu_names = {e.name for e in MENU}
        assert name not in menu_names, (
            f"unexpected MenuEntry.name conflict with security redirect: "
            f"{name!r} present in MENU"
        )

    def test_idempotent_on_bare_name(self):
        """Running the helper twice produces the same result."""
        first = endpoint_to_view_name("preferences.profile")
        second = endpoint_to_view_name(first)
        assert first == second == "profile"


class TestEndpointToViewNameInputTolerance:
    """Defensive cases — none should raise. Flask endpoints are
    user-string-ish in error cases (404 with custom error handlers,
    raw URLs in dev, etc.)."""

    def test_starts_with_dot(self):
        """`".profile"` — leading dot, no blueprint name. Should
        return `"profile"`."""
        assert endpoint_to_view_name(".profile") == "profile"

    def test_ends_with_dot(self):
        """`"preferences."` — trailing dot. The split picks the
        empty suffix."""
        assert endpoint_to_view_name("preferences.") == ""

    def test_only_dot(self):
        assert endpoint_to_view_name(".") == ""

    def test_no_dot_long_name(self):
        """Long view names without a blueprint prefix pass through
        unchanged."""
        assert endpoint_to_view_name("very_long_view_name") == "very_long_view_name"
