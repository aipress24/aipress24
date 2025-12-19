# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wire/views/_filters.py

Tests the pure state manipulation logic of FilterBar without Flask dependencies.
"""

from __future__ import annotations

from app.modules.wire.views._filters import (
    FILTER_SPECS,
    FILTER_TAG_LABEL,
    SORTER_OPTIONS,
    FilterBar,
)


class TestFilterConstants:
    """Test wire module filter constants."""

    def test_filter_specs_have_required_keys(self) -> None:
        """Test FILTER_SPECS have required keys."""
        for spec in FILTER_SPECS:
            assert "id" in spec
            assert "label" in spec
            assert "selector" in spec

    def test_sorter_options_are_tuples(self) -> None:
        """Test SORTER_OPTIONS are (value, label) tuples."""
        for value, label in SORTER_OPTIONS:
            assert isinstance(value, str)
            assert isinstance(label, str)


class TestFilterBarStateManipulation:
    """Test FilterBar state manipulation logic.

    These tests create FilterBar instances without Flask context by bypassing
    __init__ and directly setting the state. This isolates the pure logic.
    """

    def _create_bar(self, state: dict | None = None) -> FilterBar:
        """Create a FilterBar with preset state, bypassing Flask dependencies."""
        bar = object.__new__(FilterBar)
        bar.state = state if state is not None else {}
        return bar

    def test_add_filter(self) -> None:
        """Test add_filter appends to filters list."""
        bar = self._create_bar()

        bar.add_filter("sector", "tech")

        assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]

    def test_add_multiple_filters(self) -> None:
        """Test adding multiple filters."""
        bar = self._create_bar()

        bar.add_filter("sector", "tech")
        bar.add_filter("genre", "news")

        assert len(bar.state["filters"]) == 2

    def test_has_filter_returns_true_when_present(self) -> None:
        """Test has_filter returns True for existing filter."""
        bar = self._create_bar({"filters": [{"id": "sector", "value": "tech"}]})

        assert bar.has_filter("sector", "tech") is True

    def test_has_filter_returns_false_when_absent(self) -> None:
        """Test has_filter returns False for missing filter."""
        bar = self._create_bar({"filters": []})

        assert bar.has_filter("sector", "tech") is False

    def test_remove_filter(self) -> None:
        """Test remove_filter removes matching filter."""
        bar = self._create_bar({"filters": [{"id": "sector", "value": "tech"}]})

        bar.remove_filter("sector", "tech")

        assert bar.state["filters"] == []

    def test_toggle_filter_adds_when_absent(self) -> None:
        """Test toggle_filter adds filter when not present."""
        bar = self._create_bar({"filters": []})

        bar.toggle_filter("sector", "tech")

        assert bar.has_filter("sector", "tech") is True

    def test_toggle_filter_removes_when_present(self) -> None:
        """Test toggle_filter removes filter when present."""
        bar = self._create_bar({"filters": [{"id": "sector", "value": "tech"}]})

        bar.toggle_filter("sector", "tech")

        assert bar.has_filter("sector", "tech") is False

    def test_sort_by_sets_sort_order(self) -> None:
        """Test sort_by updates state."""
        bar = self._create_bar()

        bar.sort_by("views")

        assert bar.state["sort-by"] == "views"

    def test_sort_order_returns_current_sort(self) -> None:
        """Test sort_order property returns current sort."""
        bar = self._create_bar({"sort-by": "likes"})

        assert bar.sort_order == "likes"

    def test_sort_order_defaults_to_date(self) -> None:
        """Test sort_order defaults to 'date'."""
        bar = self._create_bar()

        assert bar.sort_order == "date"

    def test_active_filters_returns_formatted_list(self) -> None:
        """Test active_filters formats filters with tag_label."""
        bar = self._create_bar({"filters": [{"id": "sector", "value": "tech"}]})

        active = bar.active_filters

        assert len(active) == 1
        assert active[0]["id"] == "sector"
        assert active[0]["value"] == "tech"
        assert active[0]["tag_label"] == FILTER_TAG_LABEL["sector"]

    def test_tag_property_returns_tag_value(self) -> None:
        """Test tag property extracts tag filter value."""
        bar = self._create_bar({"filters": [{"id": "tag", "value": "python"}]})

        assert bar.tag == "python"

    def test_tag_property_returns_empty_when_no_tag(self) -> None:
        """Test tag property returns empty string when no tag filter."""
        bar = self._create_bar({"filters": []})

        assert bar.tag == ""
