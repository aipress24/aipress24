# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/menu.py"""

from __future__ import annotations

import pytest

from app.modules.wip.constants import MenuEntry
from app.modules.wip.menu import MenuItem


def test_menu_item_requires_absolute_href() -> None:
    """Test MenuItem requires href starting with /."""
    # Valid href
    item = MenuItem(
        name="home", label="Home", icon="home-icon", href="/home", current=False
    )
    assert item.href == "/home"

    # Invalid href raises AssertionError
    with pytest.raises(AssertionError):
        MenuItem(name="bad", label="Bad", icon="x", href="relative", current=False)

    with pytest.raises(AssertionError):
        MenuItem(name="empty", label="Empty", icon="x", href="", current=False)


def test_menu_entry_creation() -> None:
    """Test MenuEntry can be created with all fields."""
    entry = MenuEntry(
        name="test",
        label="Test Label",
        icon="test-icon",
        endpoint="wip.test",
        allowed_roles=["ADMIN"],
    )

    assert entry.name == "test"
    assert entry.label == "Test Label"
    assert entry.icon == "test-icon"
    assert entry.endpoint == "wip.test"
    assert entry.allowed_roles == ["ADMIN"]


def test_menu_entry_without_roles() -> None:
    """Test MenuEntry can be created without role restrictions."""
    entry = MenuEntry(
        name="public",
        label="Public Page",
        icon="globe",
        endpoint="wip.public",
    )

    assert entry.name == "public"
    assert entry.allowed_roles is None
