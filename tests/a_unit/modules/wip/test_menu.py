# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/menu.py"""

from __future__ import annotations

import pytest

from app.modules.wip.menu import MenuItem, _get_class


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


def test_get_class_imports_from_module() -> None:
    """Test _get_class imports class from module path."""
    key = "menu:app.modules.wip.menu.MenuItem"
    cls = _get_class(key)

    assert cls is MenuItem


def test_get_class_raises_for_invalid_path() -> None:
    """Test _get_class raises appropriate errors for invalid paths."""
    with pytest.raises(AttributeError):
        _get_class("menu:app.modules.wip.menu.NonExistentClass")

    with pytest.raises(ModuleNotFoundError):
        _get_class("menu:nonexistent.module.SomeClass")
