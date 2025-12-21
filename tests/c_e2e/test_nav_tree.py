# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Robust tests for navigation tree.

These tests verify structural integrity and invariants, NOT specific values.
They should NOT break when you:
- Add or remove pages
- Change labels, icons, or order
- Reorganize menu hierarchy

They SHOULD catch:
- Broken parent references (orphaned nodes)
- Circular parent chains
- Invalid ACL rules
- Missing required sections
- Schema violations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.flask.lib.nav import nav_tree

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture(autouse=True)
def build_nav_tree(app: Flask):
    """Build the nav tree before each test."""
    # Reset the tree to ensure fresh build
    nav_tree._nodes = {}
    nav_tree._sections = {}
    nav_tree._url_to_endpoint = {}
    nav_tree._built = False

    with app.app_context():
        nav_tree.build(app)
    yield


class TestNavTreeSchemaValidity:
    """Test that all nav nodes conform to expected schema."""

    def test_all_nodes_have_name(self, app: Flask):
        """Every node must have a non-empty name."""
        for name, node in nav_tree._nodes.items():
            assert node.name, f"Node has empty name"
            assert node.name == name, f"Node name mismatch: {node.name} vs {name}"

    def test_all_nodes_have_label(self, app: Flask):
        """Every node must have a non-empty label."""
        for name, node in nav_tree._nodes.items():
            assert node.label, f"Node {name} has no label"
            assert isinstance(node.label, str), f"Node {name} label is not a string"

    def test_all_nodes_have_url_rule(self, app: Flask):
        """Every node must have a URL rule."""
        for name, node in nav_tree._nodes.items():
            assert node.url_rule, f"Node {name} has no url_rule"
            assert node.url_rule.startswith("/"), (
                f"Node {name} url_rule doesn't start with /"
            )

    def test_all_sections_are_marked(self, app: Flask):
        """All section nodes must have is_section=True."""
        for name, node in nav_tree._sections.items():
            assert node.is_section is True, f"Section {name} not marked as section"

    def test_non_section_nodes_not_marked_as_section(self, app: Flask):
        """Non-section nodes should have is_section=False."""
        for name, node in nav_tree._nodes.items():
            if name not in nav_tree._sections:
                assert node.is_section is False, (
                    f"Non-section {name} marked as section"
                )

    def test_in_menu_is_boolean(self, app: Flask):
        """in_menu must be a boolean."""
        for name, node in nav_tree._nodes.items():
            assert isinstance(node.in_menu, bool), (
                f"Node {name} in_menu is not boolean"
            )

    def test_order_is_numeric_or_none(self, app: Flask):
        """Order must be a number or None."""
        for name, node in nav_tree._nodes.items():
            if node.order is not None:
                assert isinstance(node.order, int), (
                    f"Node {name} order is not int: {type(node.order)}"
                )

    def test_icon_is_string_or_none(self, app: Flask):
        """Icon must be a string or None."""
        for name, node in nav_tree._nodes.items():
            assert node.icon is None or isinstance(node.icon, str), (
                f"Node {name} icon is neither string nor None: {type(node.icon)}"
            )


class TestNavTreeACLValidity:
    """Test that ACL rules are properly formed."""

    def test_acl_is_list(self, app: Flask):
        """ACL must be a list."""
        for name, node in nav_tree._nodes.items():
            assert isinstance(node.acl, list), (
                f"Node {name} ACL is not a list: {type(node.acl)}"
            )

    def test_acl_rules_are_3_tuples(self, app: Flask):
        """Each ACL rule must be a 3-tuple (directive, role, action)."""
        for name, node in nav_tree._nodes.items():
            for i, acl in enumerate(node.acl):
                assert len(acl) == 3, (
                    f"ACL rule {i} on {name} is not a 3-tuple: {acl}"
                )

    def test_acl_directives_are_valid(self, app: Flask):
        """ACL directives must be 'Allow' or 'Deny'."""
        valid_directives = {"Allow", "Deny"}
        for name, node in nav_tree._nodes.items():
            for directive, _role, _action in node.acl:
                assert directive in valid_directives, (
                    f"Invalid ACL directive on {name}: {directive}"
                )

    def test_acl_roles_are_role_enum(self, app: Flask):
        """ACL roles should be RoleEnum values."""
        for name, node in nav_tree._nodes.items():
            for _directive, role, _action in node.acl:
                assert isinstance(role, RoleEnum), (
                    f"ACL role on {name} is not RoleEnum: {role} ({type(role)})"
                )

    def test_acl_actions_are_strings(self, app: Flask):
        """ACL actions must be strings."""
        for name, node in nav_tree._nodes.items():
            for _directive, _role, action in node.acl:
                assert isinstance(action, str), (
                    f"ACL action on {name} is not string: {action}"
                )


class TestNavTreeStructuralIntegrity:
    """Test structural integrity of the navigation tree."""

    def test_all_parents_exist(self, app: Flask):
        """Every node with a parent must have that parent exist in the tree."""
        for name, node in nav_tree._nodes.items():
            if node.is_section:
                continue  # Sections are roots
            if node.parent:
                assert node.parent in nav_tree._nodes, (
                    f"Node {name} has parent '{node.parent}' which doesn't exist"
                )

    def test_no_self_referential_parents(self, app: Flask):
        """No node should be its own parent."""
        for name, node in nav_tree._nodes.items():
            assert node.parent != name, f"Node {name} is its own parent"

    def test_no_circular_parent_chains(self, app: Flask):
        """No circular parent references (A -> B -> C -> A)."""
        for name, node in nav_tree._nodes.items():
            visited = {name}
            current = node.parent

            while current:
                assert current not in visited, (
                    f"Circular parent chain detected: {name} -> ... -> {current}"
                )
                visited.add(current)
                parent_node = nav_tree.get(current)
                if parent_node:
                    current = parent_node.parent
                else:
                    break

    def test_parent_chain_terminates_at_section(self, app: Flask):
        """Every non-section node's parent chain should terminate at a section."""
        for name, node in nav_tree._nodes.items():
            if node.is_section:
                continue

            # Walk up the parent chain
            visited = set()
            current = node
            found_section = False

            while current and current.name not in visited:
                visited.add(current.name)
                if current.is_section:
                    found_section = True
                    break
                if not current.parent:
                    break
                current = nav_tree.get(current.parent)

            assert found_section, (
                f"Node {name} parent chain doesn't terminate at a section"
            )


class TestNavTreeCompleteness:
    """Test that required sections exist (but don't check exact content)."""

    # These are the core sections that must exist for the app to function
    REQUIRED_SECTIONS = {
        "events",
        "swork",
        "wip",
        "wire",
        "biz",
        "admin",
        "preferences",
        "search",
    }

    def test_required_sections_exist(self, app: Flask):
        """All required sections must exist."""
        existing = set(nav_tree._sections.keys())
        missing = self.REQUIRED_SECTIONS - existing
        assert not missing, f"Missing required sections: {missing}"

    def test_sections_have_url_prefix(self, app: Flask):
        """Each section should have a URL prefix."""
        for name, section in nav_tree._sections.items():
            assert section.url_rule, f"Section {name} has no URL prefix"

    def test_tree_is_not_empty(self, app: Flask):
        """The nav tree should have a reasonable number of nodes."""
        # Don't hardcode exact count, just ensure it's populated
        assert len(nav_tree._nodes) > 20, (
            f"Nav tree seems too small: {len(nav_tree._nodes)} nodes"
        )

    def test_tree_has_more_nodes_than_sections(self, app: Flask):
        """There should be more total nodes than just sections."""
        node_count = len(nav_tree._nodes)
        section_count = len(nav_tree._sections)
        assert node_count > section_count * 2, (
            f"Expected many more nodes ({node_count}) than sections ({section_count})"
        )


class TestNavTreeChildrenOf:
    """Test the children_of method returns valid results."""

    def test_children_of_returns_list(self, app: Flask):
        """children_of should return a list."""
        for section in nav_tree._sections:
            children = nav_tree.children_of(section)
            assert isinstance(children, list)

    def test_children_have_correct_parent(self, app: Flask):
        """All children should have the queried parent."""
        for section in nav_tree._sections:
            children = nav_tree.children_of(section)
            for child in children:
                assert child.parent == section, (
                    f"Child {child.name} parent is {child.parent}, expected {section}"
                )

    def test_children_are_not_sections(self, app: Flask):
        """children_of should not return section nodes."""
        for section in nav_tree._sections:
            children = nav_tree.children_of(section)
            for child in children:
                assert not child.is_section, (
                    f"children_of({section}) returned section {child.name}"
                )

    def test_children_are_in_menu(self, app: Flask):
        """children_of should only return nodes with in_menu=True."""
        for section in nav_tree._sections:
            children = nav_tree.children_of(section)
            for child in children:
                assert child.in_menu is True, (
                    f"children_of({section}) returned hidden node {child.name}"
                )


class TestBreadcrumbsValidity:
    """Test breadcrumb generation works correctly."""

    def test_breadcrumbs_for_all_nodes(self, app: Flask):
        """Should be able to build breadcrumbs for any node without error."""
        for endpoint in nav_tree._nodes:
            # Should not raise
            crumbs = nav_tree.build_breadcrumbs(endpoint, {})
            assert isinstance(crumbs, list)

    def test_breadcrumbs_have_reasonable_depth(self, app: Flask):
        """Breadcrumbs should not be excessively deep (indicates cycle)."""
        max_depth = 10
        for endpoint in nav_tree._nodes:
            crumbs = nav_tree.build_breadcrumbs(endpoint, {})
            assert len(crumbs) <= max_depth, (
                f"Breadcrumbs too deep for {endpoint}: {len(crumbs)} levels"
            )

    def test_breadcrumbs_current_is_last(self, app: Flask):
        """The current breadcrumb should always be the last one."""
        for endpoint in nav_tree._nodes:
            crumbs = nav_tree.build_breadcrumbs(endpoint, {})
            if crumbs:
                assert crumbs[-1].current is True, (
                    f"Last breadcrumb for {endpoint} is not marked current"
                )

    def test_breadcrumbs_non_current_are_not_last(self, app: Flask):
        """Non-current breadcrumbs should not be marked current."""
        for endpoint in nav_tree._nodes:
            crumbs = nav_tree.build_breadcrumbs(endpoint, {})
            for crumb in crumbs[:-1]:  # All except last
                assert crumb.current is False, (
                    f"Non-last breadcrumb for {endpoint} marked as current"
                )

    def test_breadcrumbs_have_labels(self, app: Flask):
        """All breadcrumbs should have non-empty labels."""
        for endpoint in nav_tree._nodes:
            crumbs = nav_tree.build_breadcrumbs(endpoint, {})
            for crumb in crumbs:
                assert crumb.label, (
                    f"Breadcrumb for {endpoint} has empty label"
                )


class TestNavNodeVisibility:
    """Test NavNode visibility based on ACL.

    Note: These tests verify the visibility logic without requiring database.
    """

    def test_nodes_without_acl_are_visible(self, app: Flask):
        """Nodes without ACL rules should be visible to any user."""
        # Find nodes without ACL
        nodes_without_acl = [
            node for node in nav_tree._nodes.values() if not node.acl
        ]

        # There should be some nodes without ACL restrictions
        assert len(nodes_without_acl) > 0, "Expected some nodes without ACL"

        # All of them should return True for visibility with any mock user
        class MockUser:
            pass

        for node in nodes_without_acl:
            assert node.is_visible_to(MockUser()) is True, (
                f"Node {node.name} without ACL should be visible"
            )

    def test_nodes_with_acl_exist(self, app: Flask):
        """There should be some nodes with ACL restrictions."""
        nodes_with_acl = [
            node for node in nav_tree._nodes.values() if node.acl
        ]
        # We expect at least some protected nodes
        assert len(nodes_with_acl) > 0, "Expected some nodes with ACL"

    def test_acl_protected_nodes_have_allow_rules(self, app: Flask):
        """Nodes with ACL should have at least one Allow rule."""
        for name, node in nav_tree._nodes.items():
            if node.acl:
                allow_rules = [
                    acl for acl in node.acl if acl[0] == "Allow"
                ]
                assert allow_rules, (
                    f"Node {name} has ACL but no Allow rules"
                )


class TestNavTreeGet:
    """Test the get() method."""

    def test_get_existing_node(self, app: Flask):
        """get() should return the node for existing endpoints."""
        for endpoint in nav_tree._nodes:
            node = nav_tree.get(endpoint)
            assert node is not None
            assert node.name == endpoint

    def test_get_nonexistent_node(self, app: Flask):
        """get() should return None for non-existent endpoints."""
        node = nav_tree.get("nonexistent.endpoint")
        assert node is None

    def test_get_section(self, app: Flask):
        """get() should return section nodes."""
        for section_name in nav_tree._sections:
            node = nav_tree.get(section_name)
            assert node is not None
            assert node.is_section is True


class TestNavTreeBuild:
    """Test the build() method behavior."""

    def test_build_is_idempotent(self, app: Flask):
        """Building the tree multiple times should not change it."""
        initial_count = len(nav_tree._nodes)
        initial_sections = set(nav_tree._sections.keys())

        # Build again
        with app.app_context():
            nav_tree.build(app)

        assert len(nav_tree._nodes) == initial_count
        assert set(nav_tree._sections.keys()) == initial_sections

    def test_built_flag_is_set(self, app: Flask):
        """After building, the _built flag should be True."""
        assert nav_tree._built is True
