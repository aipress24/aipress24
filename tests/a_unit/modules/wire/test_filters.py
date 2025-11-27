# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wire/pages/_filters.py"""

from __future__ import annotations

from app.modules.wire.pages._filters import (
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

    assert not bar.has_filter("sector", "tech")

    bar.add_filter("sector", "tech")
    assert bar.has_filter("sector", "tech")

    bar.toggle_filter("sector", "tech")
    assert not bar.has_filter("sector", "tech")

    bar.toggle_filter("topic", "news")
    assert bar.has_filter("topic", "news")


def test_filter_bar_sort_and_properties() -> None:
    """Test FilterBar sort_by and property accessors."""
    bar = FilterBar.__new__(FilterBar)
    bar.state = {"filters": [{"id": "sector", "value": "tech"}], "sort-by": "views"}

    # Sort order
    bar.sort_by("date")
    assert bar.sort_order == "date"

    # Active filters with tag labels
    bar.state["sort-by"] = "views"
    active = bar.active_filters
    assert len(active) == 1 and active[0]["tag_label"] == "secteur"

    # Tag property
    bar.state = {"filters": [{"id": "tag", "value": "python"}]}
    assert bar.tag == "python"
    bar.state = {"filters": []}
    assert bar.tag == ""

    # Sorter options with selected state
    bar.state = {"sort-by": "views"}
    sorter = bar.sorter
    assert any(o["value"] == "views" and o["selected"] for o in sorter["options"])
