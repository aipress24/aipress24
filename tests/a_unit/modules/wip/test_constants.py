# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Invariant pinning for app.modules.wip.constants.

The WIP module's main navigation is declared declaratively in `constants.py`
as a list of `MenuEntry` named tuples. These constants drive the rendering of
the top-level WIP menu (Dashboard, Newsroom, Com'room, Event'room, Billing,
WORK/Achats, WORK/Ventes...) and a regression here would silently break
navigation for every press/PR user.

This file pins the *contract* of that module:
- the shape of `MenuEntry`,
- the presence and types of every public constant (MENU, BLUEPRINT_NAME),
- structural invariants that the rest of the codebase relies on:
  uniqueness of menu names/endpoints, non-empty French labels, the mutual
  exclusivity (or at least consistency) of `allowed_roles` and
  `allowed_check`, and the fact that callable gates are real callables.

We intentionally do not pin the *exact* set of menu entries (that list will
grow) — only the structural rules that every entry must satisfy.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.modules.wip import constants
from app.modules.wip.constants import BLUEPRINT_NAME, MENU, MenuEntry
from app.modules.wip.pr_access import (
    user_can_access_comroom,
    user_can_access_eventroom,
    user_can_access_newsroom,
)


class TestModuleSurface:
    """The public surface of `constants` must remain stable.

    Downstream callers (menu builder, blueprint registration) import these
    names directly. Renaming or removing one would break the WIP module at
    import time, so we pin presence and basic typing here.
    """

    def test_menu_is_a_list(self) -> None:
        assert isinstance(MENU, list)

    def test_menu_is_non_empty(self) -> None:
        """An empty MENU would render an empty sidebar for every user."""
        assert len(MENU) > 0

    def test_blueprint_name_is_str(self) -> None:
        assert isinstance(BLUEPRINT_NAME, str)

    def test_blueprint_name_value(self) -> None:
        """The blueprint name is used as a URL prefix and endpoint namespace.

        Changing it is a breaking change for every `url_for("wip.*")` call
        in the codebase, so we pin the exact value.
        """
        assert BLUEPRINT_NAME == "wip"

    def test_blueprint_name_has_no_surrounding_whitespace(self) -> None:
        assert BLUEPRINT_NAME.strip() == BLUEPRINT_NAME

    def test_blueprint_name_is_lowercase_identifier(self) -> None:
        """Flask endpoint prefixes should be lowercase identifiers."""
        assert BLUEPRINT_NAME.isidentifier()
        assert BLUEPRINT_NAME.islower()

    def test_menu_entry_is_exported(self) -> None:
        assert hasattr(constants, "MenuEntry")
        assert MenuEntry is constants.MenuEntry


class TestMenuEntryShape:
    """`MenuEntry` is a NamedTuple — its field order is part of the contract.

    Several call sites unpack it positionally; reordering fields would
    silently corrupt menu rendering.
    """

    def test_is_namedtuple(self) -> None:
        assert issubclass(MenuEntry, tuple)
        assert hasattr(MenuEntry, "_fields")

    def test_field_order(self) -> None:
        assert MenuEntry._fields == (
            "name",
            "label",
            "icon",
            "endpoint",
            "allowed_roles",
            "allowed_check",
        )

    def test_optional_fields_have_none_defaults(self) -> None:
        """`allowed_roles` and `allowed_check` are optional; everything else
        is required at construction time."""
        entry = MenuEntry(name="x", label="X", icon="i", endpoint="wip.x")
        assert entry.allowed_roles is None
        assert entry.allowed_check is None

    def test_required_fields_are_required(self) -> None:
        with pytest.raises(TypeError):
            MenuEntry(name="x", label="X", icon="i")  # type: ignore[call-arg]  # ty:ignore[missing-argument]


class TestMenuEntries:
    """Every entry in MENU must satisfy the structural rules used by the
    menu renderer: non-empty trimmed strings for the visible attributes and
    an endpoint that lives in a Flask blueprint namespace."""

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_entry_is_menu_entry(self, entry: MenuEntry) -> None:
        assert isinstance(entry, MenuEntry)

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_string_fields_are_non_empty(self, entry: MenuEntry) -> None:
        """Empty strings would render an invisible/broken menu item."""
        for field in ("name", "label", "icon", "endpoint"):
            value = getattr(entry, field)
            assert isinstance(value, str), f"{entry.name}.{field} must be str"
            assert value, f"{entry.name}.{field} must be non-empty"

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_string_fields_have_no_surrounding_whitespace(
        self, entry: MenuEntry
    ) -> None:
        """Trailing whitespace in labels/icons is a copy-paste smell that
        breaks CSS class lookups for icons."""
        for field in ("name", "label", "icon", "endpoint"):
            value = getattr(entry, field)
            assert value == value.strip(), f"{entry.name}.{field} has whitespace"

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_name_is_identifier_like(self, entry: MenuEntry) -> None:
        """Menu names appear in template lookups; allow letters, digits,
        underscores and hyphens (e.g. `bw-activation`) — but no spaces."""
        assert " " not in entry.name
        assert entry.name == entry.name.lower()

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_endpoint_is_namespaced(self, entry: MenuEntry) -> None:
        """Flask endpoints used by the menu must include a blueprint
        prefix (`<blueprint>.<view>`)."""
        assert "." in entry.endpoint, f"{entry.name}: endpoint missing namespace"
        prefix, _, view = entry.endpoint.partition(".")
        assert prefix, f"{entry.name}: empty blueprint prefix"
        assert view, f"{entry.name}: empty view name"

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_allowed_roles_shape(self, entry: MenuEntry) -> None:
        """`allowed_roles`, when set, must be a non-empty list of non-empty
        upper-case role strings."""
        if entry.allowed_roles is None:
            return
        assert isinstance(entry.allowed_roles, list)
        assert len(entry.allowed_roles) > 0
        for role in entry.allowed_roles:
            assert isinstance(role, str) and role
            assert role == role.strip()
            assert role.isupper(), f"role {role!r} should be UPPER_CASE"

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_allowed_check_is_callable(self, entry: MenuEntry) -> None:
        if entry.allowed_check is not None:
            assert callable(entry.allowed_check)


class TestMenuInvariants:
    """Cross-entry invariants that the menu builder depends on."""

    def test_names_are_unique(self) -> None:
        """`name` is used as the DOM id/key for the menu item — duplicates
        would collapse two distinct entries."""
        names = [e.name for e in MENU]
        assert len(names) == len(set(names))

    def test_endpoints_are_unique(self) -> None:
        """Two menu items pointing at the same endpoint would both light up
        as `current` on the same page."""
        endpoints = [e.endpoint for e in MENU]
        assert len(endpoints) == len(set(endpoints))

    def test_dashboard_is_first(self) -> None:
        """UX contract: the dashboard is the landing entry of WIP."""
        assert MENU[0].name == "dashboard"

    def test_known_entries_present(self) -> None:
        """These entries are referenced from templates / other modules and
        their disappearance would be a regression."""
        names = {e.name for e in MENU}
        expected = {
            "dashboard",
            "newsroom",
            "comroom",
            "eventroom",
            "opportunities",
            "bw-activation",
            "billing",
            "achats",
            "ventes",
            "performance",
        }
        missing = expected - names
        assert not missing, f"missing menu entries: {missing}"

    def test_rooms_use_callable_gate(self) -> None:
        """Newsroom/Com'room/Event'room access depends on the user's PR
        profile, not on a flat role list — the gate must be the dedicated
        predicate from `pr_access`, not a stale role list."""
        by_name = {e.name: e for e in MENU}
        expected_gates: dict[str, Callable] = {
            "newsroom": user_can_access_newsroom,
            "comroom": user_can_access_comroom,
            "eventroom": user_can_access_eventroom,
        }
        for name, gate in expected_gates.items():
            entry = by_name[name]
            assert entry.allowed_check is gate
            # And these rooms must not also carry a stale role allow-list.
            assert entry.allowed_roles is None

    def test_ventes_restricted_to_press_media(self) -> None:
        """Ticket #0192: only PRESS_MEDIA users see the WORK/Ventes tab."""
        ventes = next(e for e in MENU if e.name == "ventes")
        assert ventes.allowed_roles == ["PRESS_MEDIA"]
        assert ventes.allowed_check is None

    def test_dashboard_restricted_to_press_and_academic(self) -> None:
        dashboard = next(e for e in MENU if e.name == "dashboard")
        assert dashboard.allowed_roles == ["PRESS_MEDIA", "ACADEMIC"]

    def test_bw_activation_uses_external_blueprint(self) -> None:
        """The Business Wall entry points at the `bw_activation` blueprint
        (not `wip`) — the menu intentionally crosses module boundaries
        here."""
        bw = next(e for e in MENU if e.name == "bw-activation")
        assert bw.endpoint == "bw_activation.index"


class TestFrenchLabels:
    """The UI is in French — pin a few representative labels so a careless
    rename ("Tableau de bord" -> "Dashboard") is caught."""

    @pytest.mark.parametrize(
        ("name", "expected_label"),
        [
            ("dashboard", "Tableau de bord"),
            ("opportunities", "Opportunités"),
            ("billing", "Facturation"),
            ("achats", "Achats"),
            ("ventes", "Ventes"),
            ("performance", "Performance"),
            ("bw-activation", "Business Wall"),
        ],
    )
    def test_label(self, name: str, expected_label: str) -> None:
        entry = next(e for e in MENU if e.name == name)
        assert entry.label == expected_label

    @pytest.mark.parametrize("entry", MENU, ids=lambda e: e.name)
    def test_label_is_non_empty_string(self, entry: MenuEntry) -> None:
        assert isinstance(entry.label, str)
        assert entry.label.strip() == entry.label
        assert entry.label
