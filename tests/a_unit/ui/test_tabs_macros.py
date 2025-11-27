# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ui/macros/tabs.py"""

from __future__ import annotations

from app.ui.macros.tabs import m_tab, m_tab_bar, m_tabs


def test_m_tab_renders_with_href_and_label() -> None:
    """Test m_tab renders anchor with href and label."""
    tab = {"href": "/test", "label": "My Label"}

    result = m_tab(tab, 0, 1)

    assert 'href="/test"' in result
    assert "My Label" in result


def test_m_tab_current_has_aria_current_page() -> None:
    """Test current tab has aria-current=page."""
    current_tab = {"href": "/test", "label": "Test", "current": True}
    non_current = {"href": "/test", "label": "Test", "current": False}

    assert 'aria-current="page"' in m_tab(current_tab, 0, 1)
    assert 'aria-current="undefined"' in m_tab(non_current, 0, 1)


def test_m_tab_with_tip_has_data_tip() -> None:
    """Test tab with tip has data-tip attribute."""
    tab = {"href": "/test", "label": "Test", "tip": "Tooltip"}

    result = m_tab(tab, 0, 1)

    assert 'data-tip="Tooltip"' in result


def test_m_tabs_creates_nav_with_tabs() -> None:
    """Test m_tabs creates nav element with correct tabs."""
    tabs = [
        {"href": "/tab1", "label": "Tab 1"},
        {"href": "/tab2", "label": "Tab 2"},
    ]

    result = m_tabs(tabs)

    assert "<nav" in result
    assert "Tab 1" in result
    assert "Tab 2" in result
    assert result.count("<a ") == 2


def test_m_tab_bar_wraps_tabs() -> None:
    """Test m_tab_bar wraps tabs in div."""
    tabs = [{"href": "/test", "label": "Test"}]

    result = m_tab_bar(tabs)

    assert "<div" in result
    assert "<nav" in result
