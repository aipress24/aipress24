# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views.

These tests verify view configuration as equivalents to removed Page class tests.
"""

from __future__ import annotations

import pytest

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

    @pytest.mark.parametrize(
        "entry_name",
        ["dashboard", "newsroom", "comroom", "eventroom", "bw-activation"],
    )
    def test_menu_has_required_entry(self, entry_name: str):
        """Test menu has required entries."""
        names = [entry.name for entry in MENU]
        assert entry_name in names

    def test_menu_entry_endpoints_start_with_wip(self):
        """Test all menu endpoints are in wip blueprint, except for link to new BW."""
        for entry in MENU:
            assert entry.endpoint.startswith("wip.") or entry.endpoint.startswith(
                "bw_activation."
            )
