# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for navigation system context injection.

These tests verify that the nav context processor correctly injects
nav_* variables into templates. This prevents UndefinedError when
templates access nav_secondary_menu, nav_main_menu, etc.
"""

from __future__ import annotations

from flask import Flask

from app.flask.lib.nav.tree import MenuItem


class TestNavTree:
    """Test that NavTree builds menus correctly."""

    def test_nav_tree_builds_main_menu(self, app: Flask):
        """Test nav_tree builds main menu from MAIN_MENU config."""
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            # Ensure nav tree is built
            if not nav_tree._built:
                nav_tree.build(app)

            menu = nav_tree.build_menu("main", "swork.swork")

            assert isinstance(menu, list)
            assert len(menu) > 0
            assert all(isinstance(item, MenuItem) for item in menu)

    def test_nav_main_menu_has_required_attributes(self, app: Flask):
        """Test main menu items have required attributes for template."""
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            if not nav_tree._built:
                nav_tree.build(app)

            menu = nav_tree.build_menu("main", "swork.swork")

            if menu:
                item = menu[0]
                assert hasattr(item, "label"), "MenuItem should have label"
                assert hasattr(item, "url"), "MenuItem should have url"
                assert hasattr(item, "active"), "MenuItem should have active"
                assert hasattr(item, "tooltip"), "MenuItem should have tooltip"

    def test_nav_user_menu_built(self, app: Flask):
        """Test nav_tree builds user menu from USER_MENU config."""
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            if not nav_tree._built:
                nav_tree.build(app)

            menu = nav_tree.build_menu("user", "swork.swork")

            assert isinstance(menu, list)
            # USER_MENU has items
            assert len(menu) > 0

    def test_nav_admin_menu_built(self, app: Flask):
        """Test nav_tree builds admin menu from ADMIN_MENU config."""
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            if not nav_tree._built:
                nav_tree.build(app)

            menu = nav_tree.build_menu("admin", "admin.dashboard")

            assert isinstance(menu, list)
            # ADMIN_MENU has items
            assert len(menu) > 0


class TestNavMenuItemStructure:
    """Test that MenuItem has all required attributes."""

    def test_menuitem_has_all_attributes(self):
        """Test MenuItem dataclass has all expected attributes."""
        item = MenuItem(
            label="Test",
            url="/test",
            icon="test-icon",
            active=True,
            tooltip="Test tooltip",
        )

        assert item.label == "Test"
        assert item.url == "/test"
        assert item.icon == "test-icon"
        assert item.active is True
        assert item.tooltip == "Test tooltip"

    def test_menuitem_defaults(self):
        """Test MenuItem has sensible defaults."""
        item = MenuItem(label="Test", url="/test")

        assert item.icon == ""
        assert item.active is False
        assert item.tooltip == ""
