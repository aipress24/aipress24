# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views.

These tests verify view configuration as equivalents to removed Page class tests.
"""

from __future__ import annotations

from app.modules.wip.constants import MENU, MenuEntry


class TestWipMenuConfiguration:
    """Test wip menu configuration - equivalent to Page attribute tests."""

    def test_menu_has_entries(self):
        """Test MENU has entries."""
        assert len(MENU) > 0

    def test_menu_entry_structure(self):
        """Test each menu entry has required fields."""
        for entry in MENU:
            assert isinstance(entry, MenuEntry)
            assert entry.name
            assert entry.label
            assert entry.icon
            assert entry.endpoint

    def test_menu_has_dashboard(self):
        """Test menu has dashboard entry."""
        names = [entry.name for entry in MENU]
        assert "dashboard" in names

    def test_menu_has_newsroom(self):
        """Test menu has newsroom entry."""
        names = [entry.name for entry in MENU]
        assert "newsroom" in names

    def test_menu_has_comroom(self):
        """Test menu has comroom entry."""
        names = [entry.name for entry in MENU]
        assert "comroom" in names

    def test_menu_has_eventroom(self):
        """Test menu has eventroom entry."""
        names = [entry.name for entry in MENU]
        assert "eventroom" in names

    def test_menu_has_business_wall(self):
        """Test menu has business wall entry (org-profile)."""
        names = [entry.name for entry in MENU]
        assert "org-profile" in names

    def test_menu_entry_endpoints_start_with_wip(self):
        """Test all menu endpoints are in wip blueprint."""
        for entry in MENU:
            assert entry.endpoint.startswith("wip.")
