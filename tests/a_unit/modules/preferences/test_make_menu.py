# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `make_menu` in `app.modules.preferences.menu`.

`make_menu(current_name)` builds the dict list the preferences side-
bar template renders. Each entry is :

- `name`    — matches the MenuEntry name (for « current page » match)
- `label`   — French user-facing label
- `icon`    — Heroicons identifier
- `href`    — built via `url_for(entry.endpoint)`
- `current` — bool, true iff `current_name == entry.name`

The function reads from `MENU` (pinned in `test_constants.py`) and
calls `url_for` per entry (needs an app context). Pin the contract :
- exactly one dict per MENU entry
- `current` is true iff names match
- `href` is built from the endpoint string
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.modules.preferences.constants import MENU
from app.modules.preferences.menu import make_menu

if TYPE_CHECKING:
    from flask import Flask


class TestMakeMenuShape:
    def test_returns_one_dict_per_menu_entry(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        assert len(menu) == len(MENU)

    def test_each_dict_has_required_keys(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        for item in menu:
            for key in ("name", "label", "icon", "href", "current"):
                assert key in item, f"Menu dict missing {key!r}: {item!r}"

    def test_keys_are_in_canonical_order(self, app: Flask):
        """The template iterates the dict.keys() implicitly — pin
        the order to match what the template's `{{ entry.label }}`
        access expects."""
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        assert list(menu[0].keys()) == ["name", "label", "icon", "href", "current"]


class TestMakeMenuCurrentFlag:
    def test_current_true_only_for_matching_name(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("invitations")
        currents = [m["name"] for m in menu if m["current"]]
        assert currents == ["invitations"]

    def test_unknown_name_marks_nothing_current(self, app: Flask):
        """`make_menu("totally-bogus")` — pin the « no match → no
        highlight » behaviour. Better than highlighting the default
        since the caller explicitly asked for something else."""
        with app.test_request_context("/preferences/"):
            menu = make_menu("totally-bogus")
        currents = [m["name"] for m in menu if m["current"]]
        assert currents == []

    @pytest.mark.parametrize(
        "name",
        [
            "profile",
            "password",
            "email",
            "invitations",
            "profile_page",
            "interests",
            "contact_options",
            "banner",
        ],
    )
    def test_every_canonical_name_can_be_current(self, app: Flask, name):
        """Pin that every canonical MenuEntry name produces exactly
        one current dict — none gets silently dropped if the
        `make_menu` impl ever filters."""
        with app.test_request_context("/preferences/"):
            menu = make_menu(name)
        currents = [m["name"] for m in menu if m["current"]]
        assert currents == [name], (
            f"name={name!r}: expected one current, got {currents}"
        )

    def test_empty_string_marks_nothing_current(self, app: Flask):
        """An empty current_name (e.g. when `endpoint` is None on a
        404 page) must NOT match the first MenuEntry."""
        with app.test_request_context("/preferences/"):
            menu = make_menu("")
        currents = [m["name"] for m in menu if m["current"]]
        assert currents == []


class TestMakeMenuLabelsAndIcons:
    def test_labels_match_menu_constant(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        by_name = {m["name"]: m["label"] for m in menu}
        for entry in MENU:
            assert by_name[entry.name] == entry.label

    def test_icons_match_menu_constant(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        by_name = {m["name"]: m["icon"] for m in menu}
        for entry in MENU:
            assert by_name[entry.name] == entry.icon


class TestMakeMenuHrefs:
    def test_href_built_from_endpoint(self, app: Flask):
        """Each `href` is `url_for(entry.endpoint)`. Pin the resolved
        URL for one canonical entry as a smoke check that the
        `url_for` call works."""
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        # Each href must be a non-empty path starting with /
        for item in menu:
            assert item["href"]
            assert item["href"].startswith("/")

    def test_each_href_unique(self, app: Flask):
        """Two menu entries pointing at the same URL would confuse
        the « current page » highlighting. Pin uniqueness as a
        cross-check that MENU's endpoint field is also unique."""
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        hrefs = [m["href"] for m in menu]
        assert len(hrefs) == len(set(hrefs)), f"Duplicate menu hrefs: {hrefs}"


class TestMakeMenuOrder:
    """The order of entries in MENU is the visual order in the
    sidebar. Pin so a refactor that walks MENU via a `set()` or
    `dict()` doesn't silently shuffle the entries."""

    def test_returns_in_menu_constant_order(self, app: Flask):
        with app.test_request_context("/preferences/"):
            menu = make_menu("profile")
        names_in_order = [m["name"] for m in menu]
        expected = [e.name for e in MENU]
        assert names_in_order == expected
