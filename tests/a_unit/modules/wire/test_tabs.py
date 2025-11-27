# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wire/pages/_tabs.py"""

from __future__ import annotations

from app.modules.wire.pages._tabs import (
    AgenciesTab,
    ComTab,
    JournalistsTab,
    MediasTab,
    WallTab,
    get_tabs,
)


def test_get_tabs_returns_all_tab_types() -> None:
    """Test get_tabs returns all expected tab instances with correct order."""
    tabs = get_tabs()

    assert len(tabs) == 5
    assert [type(t).__name__ for t in tabs] == [
        "WallTab",
        "AgenciesTab",
        "MediasTab",
        "JournalistsTab",
        "ComTab",
    ]


def test_tab_classes_have_required_attributes() -> None:
    """Test all tab classes have required attributes."""
    for tab_cls in [WallTab, AgenciesTab, MediasTab, JournalistsTab, ComTab]:
        tab = tab_cls()
        assert isinstance(tab.id, str)
        assert isinstance(tab.label, str)
        assert isinstance(tab.tip, str)
        assert isinstance(tab.post_type_allow, set)


def test_wall_and_com_tab_post_types() -> None:
    """Test WallTab and ComTab filter for correct post types."""
    assert WallTab().post_type_allow == {"article", "post"}
    assert ComTab().post_type_allow == {"press_release"}
    assert WallTab().get_authors() is None
