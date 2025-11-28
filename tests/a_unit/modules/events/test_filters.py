# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for events/pages/_filters.py"""

from __future__ import annotations

from app.modules.events.pages._filters import (
    FILTER_SPECS,
    FILTER_TAG_LABEL,
    SORTER_OPTIONS,
    FilterBar,
)


def test_filter_constants_are_consistent() -> None:
    """Test filter constants have consistent structure."""
    # FILTER_SPECS have required keys
    for spec in FILTER_SPECS:
        assert all(k in spec for k in ("id", "label", "selector"))

    # FILTER_TAG_LABEL maps all filter IDs
    assert {spec["id"] for spec in FILTER_SPECS} == set(FILTER_TAG_LABEL.keys())

    # SORTER_OPTIONS are (value, label) tuples
    assert all(len(opt) == 2 and isinstance(opt[0], str) for opt in SORTER_OPTIONS)


def test_filter_bar_filter_operations() -> None:
    """Test FilterBar add/remove/toggle filter operations."""
    bar = FilterBar.__new__(FilterBar)
    bar.state = {}

    assert not bar.has_filter("genre", "conference")

    bar.add_filter("genre", "conference")
    assert bar.has_filter("genre", "conference")

    bar.toggle_filter("genre", "conference")
    assert not bar.has_filter("genre", "conference")

    bar.toggle_filter("sector", "tech")
    assert bar.has_filter("sector", "tech")


def test_filter_bar_sort_and_properties() -> None:
    """Test FilterBar sort_by and property accessors."""
    bar = FilterBar.__new__(FilterBar)
    bar.state = {"filters": [{"id": "genre", "value": "webinar"}], "sort-by": "views"}

    # Sort order
    bar.sort_by("date")
    assert bar.sort_order == "date"

    # Active filters with tag labels
    bar.state["sort-by"] = "views"
    active = bar.active_filters
    assert len(active) == 1 and active[0]["tag_label"] == "type"

    # Tag property
    bar.state = {"filters": [{"id": "tag", "value": "ai"}]}
    assert bar.tag == "ai"
    bar.state = {"filters": []}
    assert bar.tag == ""

    # Sorter options with selected state
    bar.state = {"sort-by": "likes"}
    sorter = bar.sorter
    assert any(o["value"] == "likes" and o["selected"] for o in sorter["options"])


def test_filter_bar_reset() -> None:
    """Test FilterBar.reset clears state."""
    bar = FilterBar.__new__(FilterBar)
    bar.state = {"filters": [{"id": "sector", "value": "tech"}], "sort-by": "views"}

    bar.reset()

    assert bar.state == {}
