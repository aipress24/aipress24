# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Gap coverage for the nav tree module.

The existing ``tests/a_unit/test_nav_tree.py`` exercises structural
invariants against the live application's NavTree.  It leaves several
branches uncovered: ACL visibility paths (Allow / Deny / SELF / unknown
directive), ACL inheritance edge cases (cycles, missing parents,
section ACL propagation), the ``_infer_parent`` override branches,
``_validate`` warning emission, breadcrumb fallback paths,
``build_menu`` sub-cases (main / static / section), ``_is_active``
ancestry walk and the ``get_nav_tree`` module-level helper.

These tests use real ``NavTree`` / ``NavNode`` / ``NavConfig`` objects
constructed in-memory (no test doubles via mock libraries, no global
state patching) plus simple stub "user" objects (Protocol-compatible
duck types).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from flask import Blueprint, Flask, g as flask_g

from app.enums import RoleEnum
from app.flask.lib.nav import register_nav, registry as nav_registry
from app.flask.lib.nav.registry import configure_nav, get_nav_config
from app.flask.lib.nav.tree import BreadCrumb, NavNode, NavTree, get_nav_tree

if TYPE_CHECKING:
    from collections.abc import Iterable


@pytest.fixture
def preserve_registry():
    """Snapshot the global nav registry and restore it after the test.

    Several tests below mutate the registry to register throw-away
    blueprints; we must not pollute the live app's registry that other
    tests depend on.
    """
    saved = dict(nav_registry._NAV_REGISTRY)
    try:
        yield
    finally:
        nav_registry._NAV_REGISTRY.clear()
        nav_registry._NAV_REGISTRY.update(saved)


# ---------------------------------------------------------------------------
# Stub users -- real-fake collaborators implementing the duck type that
# ``has_role`` / ``is_visible_to`` expect.  No magic test doubles.
# ---------------------------------------------------------------------------


@dataclass
class StubUser:
    """Minimal user stub matching the Flask-Security User duck type."""

    role_names: tuple[str, ...] = ()
    is_anonymous: bool = False

    def has_role(self, role: Any) -> bool:
        if isinstance(role, RoleEnum):
            return role.name in self.role_names
        if isinstance(role, str):
            return role in self.role_names
        return False


@dataclass
class AnonymousStubUser:
    is_anonymous: bool = True
    role_names: tuple[str, ...] = ()

    def has_role(self, role: Any) -> bool:  # pragma: no cover - never visible
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tree(*nodes: NavNode, sections: Iterable[str] = ()) -> NavTree:
    """Build a NavTree from explicit nodes without invoking ``build()``."""
    tree = NavTree()
    for node in nodes:
        tree._nodes[node.name] = node
        if node.is_section:
            tree._sections[node.name] = node
    for name in sections:
        node = tree._nodes[name]
        node.is_section = True
        tree._sections[name] = node
    tree._build_url_index()
    tree._built = True
    return tree


# ---------------------------------------------------------------------------
# NavNode.is_visible_to -- ACL branches
# ---------------------------------------------------------------------------


class TestIsVisibleTo:
    """Exercise every ACL directive branch (lines 70-86)."""

    def test_no_acl_visible_to_anyone(self):
        node = NavNode(name="x.y", label="Y", url_rule="/y/")
        assert node.is_visible_to(StubUser()) is True
        assert node.is_visible_to(AnonymousStubUser()) is True

    def test_deny_directive_short_circuits(self):
        node = NavNode(
            name="x.y",
            label="Y",
            url_rule="/y/",
            acl=[("Deny", RoleEnum.ADMIN, "view")],
        )
        # Even an admin must be denied when the directive says so.
        admin = StubUser(role_names=(RoleEnum.ADMIN.name,))
        assert node.is_visible_to(admin) is False

    def test_allow_role_match(self):
        node = NavNode(
            name="x.y",
            label="Y",
            url_rule="/y/",
            acl=[("Allow", RoleEnum.ADMIN, "view")],
        )
        admin = StubUser(role_names=(RoleEnum.ADMIN.name,))
        non_admin = StubUser(role_names=())
        assert node.is_visible_to(admin) is True
        # No match -> default deny.
        assert node.is_visible_to(non_admin) is False

    def test_allow_self_for_authenticated_user(self):
        node = NavNode(
            name="x.y",
            label="Y",
            url_rule="/y/",
            acl=[("Allow", RoleEnum.SELF, "view")],
        )
        # Authenticated -> visible.
        assert node.is_visible_to(StubUser(is_anonymous=False)) is True
        # Anonymous -> SELF gate falls through, default deny.
        assert node.is_visible_to(AnonymousStubUser()) is False

    def test_directive_case_insensitive(self):
        node = NavNode(
            name="x.y",
            label="Y",
            url_rule="/y/",
            acl=[("allow", RoleEnum.ADMIN, "view")],
        )
        assert node.is_visible_to(StubUser(role_names=(RoleEnum.ADMIN.name,))) is True

    def test_unknown_directive_falls_through_to_default_deny(self):
        # Neither "Allow" nor "Deny" -> nothing matches -> default deny.
        node = NavNode(
            name="x.y",
            label="Y",
            url_rule="/y/",
            acl=[("Maybe", RoleEnum.ADMIN, "view")],
        )
        assert node.is_visible_to(StubUser(role_names=(RoleEnum.ADMIN.name,))) is False

    def test_effective_acl_uses_inherited_when_no_own(self):
        node = NavNode(name="x.y", label="Y", url_rule="/y/")
        node.inherited_acl = [("Allow", RoleEnum.ADMIN, "view")]
        admin = StubUser(role_names=(RoleEnum.ADMIN.name,))
        assert node.is_visible_to(admin) is True
        assert node.is_visible_to(StubUser()) is False


# ---------------------------------------------------------------------------
# NavNode.url_for -- section vs page, exception path
# ---------------------------------------------------------------------------


class TestNavNodeUrlFor:
    def test_section_returns_url_rule_directly(self):
        section = NavNode(
            name="events", label="Events", url_rule="/events", is_section=True
        )
        # No app context required since we never call url_for() for sections.
        assert section.url_for() == "/events"

    def test_page_with_unknown_endpoint_returns_hash(self, app: Flask) -> None:
        # Page node whose endpoint doesn't exist in the app's url_map:
        # url_for raises BuildError, swallowed -> "#".
        node = NavNode(
            name="totally.unknown.endpoint",
            label="E",
            url_rule="/x/<int:id>",
        )
        with app.test_request_context("/"):
            assert node.url_for(id=1) == "#"


# ---------------------------------------------------------------------------
# _infer_parent overrides
# ---------------------------------------------------------------------------


class TestInferParent:
    """Cover the explicit override branches of ``_infer_parent``."""

    def test_override_equal_to_section_points_to_section(self):
        tree = NavTree()
        # /events with parent override "events" (same as section)
        result = tree._infer_parent("/events/x", "events", override="events")
        assert result == "events"

    def test_override_without_dot_is_prefixed_with_section(self):
        tree = NavTree()
        result = tree._infer_parent("/events/x", "events", override="calendar")
        assert result == "events.calendar"

    def test_override_with_dot_returned_verbatim(self):
        tree = NavTree()
        result = tree._infer_parent("/something/", "events", override="wire.article")
        assert result == "wire.article"

    def test_no_override_top_level_returns_section(self):
        tree = NavTree()
        # Single-segment URL -> top of section.
        assert tree._infer_parent("/events/", "events", override=None) == "events"

    def test_no_override_unknown_parent_falls_back_to_section(self):
        tree = NavTree()
        # No entry in the index -> falls back to section root (line 277).
        result = tree._infer_parent("/events/calendar/", "events", override=None)
        assert result == "events"

    def test_no_override_uses_url_index_when_available(self):
        # Pre-populate the index so the URL lookup hits.
        parent = NavNode(
            name="events.list", label="List", url_rule="/events/", is_section=False
        )
        section = NavNode(
            name="events",
            label="Events",
            url_rule="/events",
            is_section=True,
        )
        tree = _make_tree(section, parent, sections=("events",))

        # /events/123 (URL param) -> /events/ -> events.list
        result = tree._infer_parent("/events/<int:id>", "events", override=None)
        assert result == "events.list"

    def test_no_override_static_segment_resolves_via_url_index(self):
        parent = NavNode(name="events.list", label="L", url_rule="/events/")
        section = NavNode(name="events", label="E", url_rule="/events", is_section=True)
        tree = _make_tree(section, parent, sections=("events",))
        result = tree._infer_parent("/events/calendar/", "events", override=None)
        assert result == "events.list"


# ---------------------------------------------------------------------------
# _infer_label
# ---------------------------------------------------------------------------


class TestInferLabel:
    def test_override_wins(self):
        tree = NavTree()

        def view():
            """First line."""

        assert tree._infer_label(view, override="Force") == "Force"

    def test_docstring_first_line(self):
        tree = NavTree()

        def view():
            """My label

            additional details.
            """

        assert tree._infer_label(view, override=None) == "My label"

    def test_fallback_to_titleized_function_name(self):
        tree = NavTree()

        def my_event_view():  # no docstring
            return None

        assert tree._infer_label(my_event_view, override=None) == "My Event View"


# ---------------------------------------------------------------------------
# _validate -- warning emission
# ---------------------------------------------------------------------------


class TestValidate:
    def test_emits_warning_for_orphan_parent(self):
        node = NavNode(
            name="ghost.page",
            label="Ghost",
            url_rule="/ghost/page/",
            parent="missing.parent",
        )
        tree = NavTree()
        tree._nodes[node.name] = node

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tree._validate()

        assert any("missing.parent" in str(w.message) for w in caught)

    def test_section_nodes_are_skipped(self):
        section = NavNode(
            name="s",
            label="S",
            url_rule="/s",
            parent="does-not-exist",
            is_section=True,
        )
        tree = NavTree()
        tree._nodes[section.name] = section
        tree._sections[section.name] = section
        # Should be a no-op for sections.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tree._validate()
        assert not caught


# ---------------------------------------------------------------------------
# ACL inheritance: cycle and unknown parent branches
# ---------------------------------------------------------------------------


class TestAclInheritance:
    def test_section_acl_propagates_to_children(self):
        section = NavNode(
            name="admin",
            label="Admin",
            url_rule="/admin",
            is_section=True,
            acl=[("Allow", RoleEnum.ADMIN, "view")],
        )
        child = NavNode(
            name="admin.dashboard",
            label="Dashboard",
            url_rule="/admin/dashboard/",
            parent="admin",
        )
        tree = _make_tree(section, child, sections=("admin",))
        tree._propagate_acl()

        assert child.inherited_acl == section.acl
        assert child.acl_source == "admin"

    def test_node_with_own_acl_not_overwritten(self):
        section = NavNode(
            name="admin",
            label="Admin",
            url_rule="/admin",
            is_section=True,
            acl=[("Allow", RoleEnum.ADMIN, "view")],
        )
        own_acl: list[tuple[str, Any, str]] = [
            ("Allow", RoleEnum.SELF, "view"),
        ]
        child = NavNode(
            name="admin.profile",
            label="Profile",
            url_rule="/admin/profile/",
            parent="admin",
            acl=own_acl,
        )
        tree = _make_tree(section, child, sections=("admin",))
        tree._propagate_acl()

        assert child.inherited_acl == []
        assert child.acl_source is None
        assert child.acl == own_acl

    def test_inheritance_walks_up_multiple_levels(self):
        section = NavNode(
            name="admin",
            label="Admin",
            url_rule="/admin",
            is_section=True,
            acl=[("Allow", RoleEnum.ADMIN, "view")],
        )
        mid = NavNode(
            name="admin.users",
            label="Users",
            url_rule="/admin/users/",
            parent="admin",
        )
        leaf = NavNode(
            name="admin.user_edit",
            label="Edit",
            url_rule="/admin/users/<int:id>",
            parent="admin.users",
        )
        tree = _make_tree(section, mid, leaf, sections=("admin",))
        tree._propagate_acl()
        assert leaf.acl_source == "admin"
        assert leaf.inherited_acl == section.acl

    def test_inheritance_stops_when_parent_missing(self):
        # Parent reference points to a node that isn't in the tree.
        orphan = NavNode(
            name="x.y",
            label="Y",
            url_rule="/x/y/",
            parent="ghost",
        )
        tree = NavTree()
        tree._nodes[orphan.name] = orphan
        tree._build_url_index()
        # _propagate_acl shouldn't blow up.
        tree._propagate_acl()
        assert orphan.inherited_acl == []
        assert orphan.acl_source is None

    def test_inheritance_breaks_on_cycle(self):
        # a -> b -> a (cycle).  Neither has ACL.
        a = NavNode(name="a.one", label="A", url_rule="/a/", parent="a.two")
        b = NavNode(name="a.two", label="B", url_rule="/b/", parent="a.one")
        tree = NavTree()
        tree._nodes[a.name] = a
        tree._nodes[b.name] = b
        tree._build_url_index()
        # Must terminate (visited-set guard) -- no ACL found.
        acl, source = tree._find_inherited_acl(a)
        assert acl == []
        assert source is None


# ---------------------------------------------------------------------------
# children_of: ordering & filtering
# ---------------------------------------------------------------------------


class TestChildrenOf:
    def test_orders_by_order_then_label(self):
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        # Same order -> tie-break by label alphabetically.
        b = NavNode(name="s.b", label="Beta", url_rule="/s/b/", parent="s", order=10)
        a = NavNode(name="s.a", label="Alpha", url_rule="/s/a/", parent="s", order=10)
        # Lower order wins.
        first = NavNode(
            name="s.first", label="Z", url_rule="/s/first/", parent="s", order=1
        )
        tree = _make_tree(section, b, a, first, sections=("s",))
        children = tree.children_of("s")
        names = [n.name for n in children]
        assert names == ["s.first", "s.a", "s.b"]

    def test_hidden_children_excluded(self):
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        visible = NavNode(name="s.v", label="V", url_rule="/s/v/", parent="s")
        hidden = NavNode(
            name="s.h",
            label="H",
            url_rule="/s/h/",
            parent="s",
            in_menu=False,
        )
        tree = _make_tree(section, visible, hidden, sections=("s",))
        children = tree.children_of("s")
        assert [n.name for n in children] == ["s.v"]

    def test_section_children_excluded(self):
        # Two sections, both "child" of root logically.  children_of should
        # never yield section nodes even when they share a parent name.
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        sub_section = NavNode(
            name="t",
            label="T",
            url_rule="/t",
            parent="s",
            is_section=True,
        )
        page = NavNode(name="s.p", label="P", url_rule="/s/p/", parent="s")
        tree = _make_tree(section, sub_section, page, sections=("s", "t"))
        children = tree.children_of("s")
        assert [n.name for n in children] == ["s.p"]


# ---------------------------------------------------------------------------
# build_breadcrumbs -- edge cases
# ---------------------------------------------------------------------------


class TestBuildBreadcrumbs:
    def test_unknown_endpoint_returns_empty(self):
        tree = NavTree()
        assert tree.build_breadcrumbs("nope.nope", {}) == []

    def test_label_override_used_for_current(self):
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        leaf = NavNode(name="s.leaf", label="Leaf", url_rule="/s/leaf/", parent="s")
        tree = _make_tree(section, leaf, sections=("s",))
        crumbs = tree.build_breadcrumbs("s.leaf", {}, label_override="Dynamic Title")
        assert crumbs[-1].label == "Dynamic Title"
        assert crumbs[-1].current is True

    def test_parent_override_redirects_chain(self):
        section_a = NavNode(name="a", label="A", url_rule="/a", is_section=True)
        section_b = NavNode(name="b", label="B", url_rule="/b", is_section=True)
        page = NavNode(name="a.page", label="P", url_rule="/a/p/", parent="a")
        tree = _make_tree(section_a, section_b, page, sections=("a", "b"))
        # Force the parent to be "b" instead of "a".
        crumbs = tree.build_breadcrumbs("a.page", {}, parent_override="b")
        labels = [c.label for c in crumbs]
        assert "B" in labels
        assert "A" not in labels

    def test_missing_parent_in_chain_stops_walk(self):
        # leaf -> ghost (not in tree) -> walk stops.
        leaf = NavNode(name="s.leaf", label="L", url_rule="/s/leaf/", parent="ghost")
        tree = NavTree()
        tree._nodes[leaf.name] = leaf
        tree._build_url_index()
        crumbs = tree.build_breadcrumbs("s.leaf", {})
        # Only the leaf itself should be present.
        assert len(crumbs) == 1
        assert crumbs[0].current is True

    def test_cycle_in_parent_chain_terminates(self):
        a = NavNode(name="x.a", label="A", url_rule="/x/a/", parent="x.b")
        b = NavNode(name="x.b", label="B", url_rule="/x/b/", parent="x.a")
        tree = NavTree()
        tree._nodes[a.name] = a
        tree._nodes[b.name] = b
        tree._build_url_index()
        # Must terminate (visited-set guards against infinite loop).
        crumbs = tree.build_breadcrumbs("x.a", {})
        # Leaf + one ancestor (then cycle detected, walk stops).
        assert all(isinstance(c, BreadCrumb) for c in crumbs)
        assert crumbs[-1].current is True


# ---------------------------------------------------------------------------
# _is_active
# ---------------------------------------------------------------------------


class TestIsActive:
    def test_same_endpoint_is_active(self):
        tree = NavTree()
        assert tree._is_active("a.b", "a.b") is True

    def test_descendant_is_active(self):
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        page = NavNode(name="s.page", label="P", url_rule="/s/p/", parent="s")
        leaf = NavNode(name="s.leaf", label="L", url_rule="/s/p/l/", parent="s.page")
        tree = _make_tree(section, page, leaf, sections=("s",))
        assert tree._is_active("s.page", "s.leaf") is True
        assert tree._is_active("s", "s.leaf") is True

    def test_unrelated_is_inactive(self):
        section = NavNode(name="s", label="S", url_rule="/s", is_section=True)
        a = NavNode(name="s.a", label="A", url_rule="/s/a/", parent="s")
        b = NavNode(name="s.b", label="B", url_rule="/s/b/", parent="s")
        tree = _make_tree(section, a, b, sections=("s",))
        assert tree._is_active("s.a", "s.b") is False

    def test_missing_current_endpoint_is_inactive(self):
        tree = NavTree()
        assert tree._is_active("a.b", "missing.endpoint") is False


# ---------------------------------------------------------------------------
# build_menu -- section submenu path (uses real app for url_for / g.user).
# Use a tiny throw-away Flask app to keep this hermetic (no DB).
# ---------------------------------------------------------------------------


def _tiny_flask_app() -> Flask:
    """Build a minimal Flask app with a couple of routes and a section."""
    app = Flask("nav_gap_app")

    bp = Blueprint("widget", __name__, url_prefix="/widget")

    @bp.route("/")
    def index():
        """Widget Index"""
        return "ok"

    @bp.route("/list/")
    def list_():
        """Widgets List"""
        return "ok"

    @bp.route("/admin/")
    def admin_page():
        """Admin Page"""
        return "ok"

    # Decorate ACL on one route via _nav_meta.
    admin_page._nav_meta = {
        "acl": [("Allow", RoleEnum.ADMIN, "view")],
    }
    # Force ordering deterministic for tests.
    list_._nav_meta = {"order": 1}
    index._nav_meta = {"order": 2}

    app.register_blueprint(bp)
    configure_nav(bp, label="Widgets", icon="cube", order=42)
    return app


class TestBuildMenuSectionSubmenu:
    """Cover the section-submenu branch of ``build_menu`` (lines 438-455)."""

    def test_submenu_filters_acl_for_user(self, preserve_registry):
        app = _tiny_flask_app()
        # Build the tree once.
        tree = NavTree()
        tree.build(app)

        non_admin = StubUser(role_names=())
        admin = StubUser(role_names=(RoleEnum.ADMIN.name,))

        with app.test_request_context("/widget/"):
            flask_g.user = non_admin
            items_non_admin = tree.build_menu("widget", "widget.index")

            flask_g.user = admin
            items_admin = tree.build_menu("widget", "widget.index")

        labels_non_admin = {item.label for item in items_non_admin}
        labels_admin = {item.label for item in items_admin}
        # The "Admin Page" item should be hidden for the non-admin.
        assert "Admin Page" in labels_admin
        assert "Admin Page" not in labels_non_admin

    def test_submenu_marks_active_node(self, preserve_registry):
        app = _tiny_flask_app()
        tree = NavTree()
        tree.build(app)

        with app.test_request_context("/widget/list/"):
            flask_g.user = StubUser(role_names=())
            items = tree.build_menu("widget", "widget.list_")

        # Find the items by label and check active flag.
        active_labels = {item.label for item in items if item.active}
        assert "Widgets List" in active_labels

    def test_submenu_without_user_does_not_filter(self, preserve_registry):
        app = _tiny_flask_app()
        tree = NavTree()
        tree.build(app)

        # No g.user set -> getattr returns None; no ACL filter applied.
        with app.test_request_context("/widget/"):
            items = tree.build_menu("widget", "widget.index")
        # All in-menu items are present.
        labels = {item.label for item in items}
        assert {"Widget Index", "Widgets List", "Admin Page"} <= labels


# ---------------------------------------------------------------------------
# build_menu -- main / user / create / admin (covers _build_main_menu,
# _build_static_menu)
# ---------------------------------------------------------------------------


class TestStaticMenus:
    """Use the real app fixture so MAIN_MENU / USER_MENU resolve real URLs."""

    def test_main_menu_marks_active_section(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            if not nav_tree._built:
                nav_tree.build(app)
            items = nav_tree.build_menu("main", "swork.member")
        # MAIN_MENU contains the swork entry; that one should be active.
        active = [i for i in items if i.active]
        assert active, "Expected at least one active main-menu entry"
        # Every menu item carries tooltip+url attributes.
        for item in items:
            assert hasattr(item, "tooltip")
            assert hasattr(item, "url")

    def test_user_menu_filters_admin_link_for_non_admin(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context(), app.test_request_context("/"):
            if not nav_tree._built:
                nav_tree.build(app)
            flask_g.user = StubUser(role_names=())
            items = nav_tree.build_menu("user", "swork.profile")

        labels = {item.label for item in items}
        # ADMIN_MENU entry requires the ADMIN role; a non-admin user must not
        # see "Administration".
        assert "Administration" not in labels

    def test_user_menu_shows_admin_link_for_admin(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context(), app.test_request_context("/"):
            if not nav_tree._built:
                nav_tree.build(app)
            flask_g.user = StubUser(role_names=(RoleEnum.ADMIN.name,))
            items = nav_tree.build_menu("user", "swork.profile")

        labels = {item.label for item in items}
        assert "Administration" in labels

    def test_user_menu_anonymous_drops_role_gated_entries(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context(), app.test_request_context("/"):
            if not nav_tree._built:
                nav_tree.build(app)
            # Anonymous flow -- no g.user attribute.
            if hasattr(flask_g, "user"):
                del flask_g.user
            items = nav_tree.build_menu("user", "swork.profile")

        labels = {item.label for item in items}
        # Without a user, role-gated entries must be dropped.
        assert "Administration" not in labels

    def test_admin_menu_supports_direct_url_entries(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context(), app.test_request_context("/"):
            if not nav_tree._built:
                nav_tree.build(app)
            flask_g.user = StubUser(role_names=(RoleEnum.ADMIN.name,))
            items = nav_tree.build_menu("admin", "admin.dashboard")

        # The ADMIN_MENU entry "Ontologie" uses a direct "/admin/ontology/"
        # URL.  Its URL should pass through verbatim (covers the
        # ``endpoint.startswith("/")`` branch).
        ontology = next((i for i in items if i.label == "Ontologie"), None)
        assert ontology is not None
        assert ontology.url == "/admin/ontology/"
        assert ontology.active is False

    def test_unknown_static_menu_name_returns_empty_list(self, app: Flask) -> None:
        nav_tree = app.extensions["nav_tree"]
        with app.app_context(), app.test_request_context("/"):
            if not nav_tree._built:
                nav_tree.build(app)
            # _build_static_menu is only called for user/create/admin; sending
            # a name that doesn't match any known menu type goes through the
            # section-submenu branch, which returns [] for unknown sections.
            assert nav_tree.build_menu("create", "anything") == []


# ---------------------------------------------------------------------------
# get_nav_tree -- module-level helper
# ---------------------------------------------------------------------------


class TestGetNavTree:
    def test_returns_tree_from_current_app(self, app: Flask) -> None:
        with app.app_context():
            tree = get_nav_tree()
        assert isinstance(tree, NavTree)
        assert tree is app.extensions["nav_tree"]

    def test_raises_when_not_registered(self) -> None:
        bare = Flask("nav_gap_bare")
        with bare.app_context(), pytest.raises(RuntimeError, match="NavTree"):
            get_nav_tree()


# ---------------------------------------------------------------------------
# register_nav + nav-config registry round-trip (sanity for build_sections)
# ---------------------------------------------------------------------------


class TestRegisterNavSmoke:
    def test_registry_round_trip(self, preserve_registry) -> None:
        bare = Flask("nav_gap_register")
        bp = Blueprint("foo", __name__, url_prefix="/foo")
        bare.register_blueprint(bp)
        configure_nav(bp, label="Foo", icon="x", order=7)

        assert get_nav_config("foo") == {
            "label": "Foo",
            "icon": "x",
            "order": 7,
            "in_menu": True,
        }

        register_nav(bare)
        # NavTree exists but isn't built yet (built lazily on first request).
        assert "nav_tree" in bare.extensions
        tree = bare.extensions["nav_tree"]
        tree.build(bare)
        section = tree.get("foo")
        assert section is not None
        assert section.is_section is True
        assert section.label == "Foo"


# ---------------------------------------------------------------------------
# build() idempotence -- second call is a no-op (line 124 / 125)
# ---------------------------------------------------------------------------


class TestBuildIdempotence:
    def test_second_build_is_no_op(self) -> None:
        tree = NavTree()
        # Pre-mark as built and stash a sentinel; build() must short-circuit.
        tree._built = True
        tree._nodes["sentinel"] = NavNode(name="sentinel", label="X", url_rule="/x/")
        # An empty Flask app -- if build() ran, it would clear or repopulate.
        empty = Flask("nav_gap_idempotent")
        tree.build(empty)
        assert "sentinel" in tree._nodes
