# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ``app.flask.lib.nav.request.NavRequest``.

WHY THIS FILE EXISTS:
    ``NavRequest`` is the request-scoped facade between Flask views and the
    navigation tree.  It is constructed implicitly via ``before_request``
    handlers in production, which makes its behaviour invisible to most of the
    integration suite.  These tests exercise the value-object surface directly
    so regressions in property accessors, dynamic-label overrides, section
    inference, and the breadcrumb/menu delegation are caught at the unit level.

    All tests are mock-free.  Where the underlying ``NavTree`` is needed we
    build a tiny throw-away Flask app with a single ``configure_nav``-ed
    blueprint, because that is the real collaborator (Pattern C - real fake).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from flask import Blueprint, Flask, g

from app.flask.lib.nav import registry as nav_registry
from app.flask.lib.nav.registry import configure_nav
from app.flask.lib.nav.request import NavRequest
from app.flask.lib.nav.tree import BreadCrumb, MenuItem, NavTree

# ----------------------------------------------------------------------------
# Real-fake collaborator: tiny Flask app + populated NavTree.
# ----------------------------------------------------------------------------


def _make_app_with_tree() -> Flask:
    """Build a minimal Flask app whose ``nav_tree`` extension is populated.

    We register a single blueprint ("shop") with one section root and a couple
    of child routes so we have a real, exercisable tree to delegate to.
    """
    app = Flask(__name__)

    bp = Blueprint("shop", __name__, url_prefix="/shop")
    configure_nav(bp, label="Shop", icon="bag", order=10)

    @bp.route("/")
    def shop() -> str:  # pragma: no cover - body unused
        """Shop home."""
        return "ok"

    @bp.route("/items/")
    def items() -> str:  # pragma: no cover - body unused
        """Items."""
        return "ok"

    @bp.route("/items/<int:id>")
    def item(id: int) -> str:  # pragma: no cover - body unused
        """Item detail."""
        return "ok"

    app.register_blueprint(bp)

    tree = NavTree()
    tree.build(app)
    app.extensions["nav_tree"] = tree

    return app


@pytest.fixture
def app_with_tree() -> Iterator[Flask]:
    """Provide a minimal Flask app with a real NavTree.

    Snapshots and restores the global nav registry so other test modules that
    rely on the production registry (built at app boot) are not affected by
    our throw-away ``configure_nav`` call.
    """
    snapshot = dict(nav_registry._NAV_REGISTRY)
    try:
        yield _make_app_with_tree()
    finally:
        nav_registry._NAV_REGISTRY.clear()
        nav_registry._NAV_REGISTRY.update(snapshot)


# ----------------------------------------------------------------------------
# Pure unit tests - no Flask context required.
# ----------------------------------------------------------------------------


class TestConstruction:
    """``NavRequest`` should faithfully store its constructor inputs."""

    def test_stores_endpoint(self) -> None:
        nav = NavRequest("shop.item", {"id": 7})
        assert nav.endpoint == "shop.item"

    def test_stores_view_args_internally(self) -> None:
        view_args: dict[str, Any] = {"id": 7, "slug": "x"}
        nav = NavRequest("shop.item", view_args)
        # The view_args dict is not exposed as a property, but it is consumed
        # by ``breadcrumbs()``.  Verifying the private attribute keeps the test
        # tied to the contract that the constructor records its inputs verbatim.
        assert nav._view_args == view_args

    def test_construction_accepts_empty_view_args(self) -> None:
        nav = NavRequest("shop.shop", {})
        assert nav._view_args == {}

    def test_overrides_start_unset(self) -> None:
        nav = NavRequest("shop.shop", {})
        assert nav.label is None
        assert nav.parent is None


class TestOverrideSetters:
    """The ``label`` and ``parent`` setters override defaults for the view."""

    def test_label_setter_round_trips(self) -> None:
        nav = NavRequest("shop.item", {})
        nav.label = "Special Item"
        assert nav.label == "Special Item"

    def test_parent_setter_round_trips(self) -> None:
        nav = NavRequest("shop.item", {})
        nav.parent = "shop.items"
        assert nav.parent == "shop.items"

    def test_label_setter_overwrites_previous_value(self) -> None:
        nav = NavRequest("shop.item", {})
        nav.label = "First"
        nav.label = "Second"
        assert nav.label == "Second"

    def test_label_and_parent_are_independent(self) -> None:
        nav = NavRequest("shop.item", {})
        nav.label = "L"
        assert nav.parent is None
        nav.parent = "P"
        assert nav.label == "L"
        assert nav.parent == "P"


class TestCurrentSection:
    """``current_section`` returns the blueprint name from the endpoint."""

    @pytest.mark.parametrize(
        ("endpoint", "expected"),
        [
            ("shop.item", "shop"),
            ("shop.items", "shop"),
            ("admin.users.edit", "admin"),  # multi-dot endpoint
            ("wire.article", "wire"),
        ],
    )
    def test_returns_part_before_first_dot(
        self, endpoint: str, expected: str
    ) -> None:
        nav = NavRequest(endpoint, {})
        assert nav.current_section == expected

    @pytest.mark.parametrize(
        "endpoint",
        ["home", "index", "ping", ""],
    )
    def test_returns_endpoint_when_no_dot(self, endpoint: str) -> None:
        nav = NavRequest(endpoint, {})
        assert nav.current_section == endpoint


# ----------------------------------------------------------------------------
# Integration with NavTree - uses a tiny throwaway Flask app.
# ----------------------------------------------------------------------------


class TestBreadcrumbsDelegation:
    """``breadcrumbs()`` should delegate to the active ``NavTree``."""

    def test_returns_list_of_breadcrumbs(self, app_with_tree: Flask) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            nav = NavRequest("shop.item", {"id": 3})
            crumbs = nav.breadcrumbs()

        assert isinstance(crumbs, list)
        assert all(isinstance(c, BreadCrumb) for c in crumbs)
        assert len(crumbs) >= 1

    def test_last_crumb_marked_current(self, app_with_tree: Flask) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            nav = NavRequest("shop.item", {"id": 3})
            crumbs = nav.breadcrumbs()

        assert crumbs[-1].current is True
        for crumb in crumbs[:-1]:
            assert crumb.current is False

    def test_label_override_propagates_to_current_crumb(
        self, app_with_tree: Flask
    ) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            nav = NavRequest("shop.item", {"id": 3})
            nav.label = "Custom Item Name"
            crumbs = nav.breadcrumbs()

        # Last crumb is the "current" one and should carry the override label
        assert crumbs[-1].label == "Custom Item Name"

    def test_unknown_endpoint_returns_empty_list(
        self, app_with_tree: Flask
    ) -> None:
        with app_with_tree.test_request_context("/nope"):
            nav = NavRequest("does.not.exist", {})
            assert nav.breadcrumbs() == []

    def test_parent_override_changes_trail(self, app_with_tree: Flask) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            # Default parent for shop.item resolves directly to the "shop"
            # section.  Override it to point at the intermediate listing page
            # and verify the trail now includes "Items.".
            nav = NavRequest("shop.item", {"id": 3})
            crumbs_default = nav.breadcrumbs()

            nav2 = NavRequest("shop.item", {"id": 3})
            nav2.parent = "shop.items"
            crumbs_overridden = nav2.breadcrumbs()

        labels_default = [c.label for c in crumbs_default]
        labels_overridden = [c.label for c in crumbs_overridden]
        assert labels_default != labels_overridden
        assert "Items." in labels_overridden
        assert "Items." not in labels_default


class TestMenuDelegation:
    """``menu()`` should delegate to the active ``NavTree``."""

    def test_defaults_to_current_section(self, app_with_tree: Flask) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            g.user = None  # no authenticated user
            nav = NavRequest("shop.item", {"id": 3})
            items = nav.menu()

        assert isinstance(items, list)
        assert all(isinstance(m, MenuItem) for m in items)

    def test_explicit_section_overrides_current(
        self, app_with_tree: Flask
    ) -> None:
        with app_with_tree.test_request_context("/shop/items/3"):
            g.user = None
            nav = NavRequest("shop.item", {"id": 3})
            # Request a different section explicitly.  No "marketing" section
            # exists, so the tree returns an empty list - but the call must
            # succeed and yield a list (not raise).
            assert nav.menu("marketing") == []

    def test_section_none_uses_current_section_property(
        self, app_with_tree: Flask
    ) -> None:
        """Verify that ``menu(None)`` matches ``menu(current_section)``."""
        with app_with_tree.test_request_context("/shop/items/3"):
            g.user = None
            nav = NavRequest("shop.items", {})
            implicit = nav.menu()
            explicit = nav.menu(nav.current_section)

        # Labels should match (active flags may differ if they depend on
        # endpoint state, but here both calls share the same endpoint)
        assert [m.label for m in implicit] == [m.label for m in explicit]

    def test_menu_marks_current_endpoint_as_active(
        self, app_with_tree: Flask
    ) -> None:
        with app_with_tree.test_request_context("/shop/items/"):
            g.user = None
            nav = NavRequest("shop.items", {})
            items = nav.menu("shop")

        # "shop.items" should appear and be marked active
        active = [m for m in items if m.active]
        assert any(a.label for a in active), (
            "Expected current endpoint to surface as an active menu item"
        )
