# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/components/filterset.py"""

from __future__ import annotations

from dataclasses import dataclass

from flask import session

from app.flask.components.filterset import Filter, FilterSet, Sorter


class TestFilter:
    """Test suite for Filter class."""

    def test_init_sets_name_and_label(self) -> None:
        """Test Filter initialization sets name and label."""
        filter = Filter("status", "Status Label")

        assert filter.name == "status"
        assert filter.label == "Status Label"
        assert filter.options == []

    def test_repr_returns_expected_format(self) -> None:
        """Test __repr__ returns expected format."""
        filter = Filter("category", "Category")

        result = repr(filter)

        assert "<Filter category Category>" == result

    def test_init_with_static_options(self) -> None:
        """Test init with provided static options."""
        filter = Filter("status", "Status")

        filter.init([], options=["Active", "Inactive", "Pending"])

        assert len(filter.options) == 3
        assert {"id": "Active", "label": "Active"} in filter.options
        assert {"id": "Inactive", "label": "Inactive"} in filter.options
        assert {"id": "Pending", "label": "Pending"} in filter.options

    def test_init_with_empty_static_options(self) -> None:
        """Test init with empty static options list."""
        filter = Filter("status", "Status")

        filter.init([], options=[])

        assert filter.options == []

    def test_init_from_objects_extracts_attribute(self) -> None:
        """Test init extracts attribute values from objects."""

        @dataclass
        class Item:
            status: str

        objects = [
            Item(status="Active"),
            Item(status="Inactive"),
            Item(status="Active"),
        ]
        filter = Filter("status", "Status")

        filter.init(objects)

        # Should be deduplicated and sorted
        assert len(filter.options) == 2
        option_ids = [o["id"] for o in filter.options]
        assert "Active" in option_ids
        assert "Inactive" in option_ids

    def test_init_from_objects_empty_list(self) -> None:
        """Test init with empty objects list."""
        filter = Filter("status", "Status")

        filter.init([])

        assert filter.options == []

    def test_init_from_objects_sorts_options(self) -> None:
        """Test init sorts options alphabetically."""

        @dataclass
        class Item:
            category: str

        objects = [
            Item(category="Zebra"),
            Item(category="Apple"),
            Item(category="Mango"),
        ]
        filter = Filter("category", "Category")

        filter.init(objects)

        option_ids = [o["id"] for o in filter.options]
        assert option_ids == ["Apple", "Mango", "Zebra"]

    def test_init_from_objects_deduplicates(self) -> None:
        """Test init removes duplicate values."""

        @dataclass
        class Item:
            type: str

        objects = [
            Item(type="A"),
            Item(type="B"),
            Item(type="A"),
            Item(type="A"),
            Item(type="B"),
        ]
        filter = Filter("type", "Type")

        filter.init(objects)

        assert len(filter.options) == 2


class TestFilterSet:
    """Test suite for FilterSet class."""

    def test_init_stores_specs(self) -> None:
        """Test FilterSet stores filter specs."""
        specs = [
            {"id": "status", "label": "Status"},
            {"id": "type", "label": "Type"},
        ]

        filter_set = FilterSet(specs)

        assert filter_set.filter_specs == specs
        assert filter_set.filters == []

    def test_init_with_empty_specs(self) -> None:
        """Test FilterSet with empty specs."""
        filter_set = FilterSet([])

        assert filter_set.filter_specs == []
        assert filter_set.filters == []

    def test_init_creates_filters_from_specs(self) -> None:
        """Test init creates Filter objects from specs."""
        specs = [
            {"id": "status", "label": "Status", "options": ["A", "B"]},
            {"id": "type", "label": "Type", "options": ["X", "Y", "Z"]},
        ]
        filter_set = FilterSet(specs)

        filter_set.init([])

        assert len(filter_set.filters) == 2
        assert filter_set.filters[0].name == "status"
        assert filter_set.filters[1].name == "type"

    def test_get_filters_returns_filter_data(self) -> None:
        """Test get_filters returns list of filter data dicts."""
        specs = [
            {"id": "status", "label": "Status", "options": ["Active", "Inactive"]},
        ]
        filter_set = FilterSet(specs)
        filter_set.init([])

        result = filter_set.get_filters()

        assert len(result) == 1
        assert result[0]["id"] == "status"
        assert result[0]["label"] == "Status"
        assert len(result[0]["options"]) == 2

    def test_get_filters_with_multiple_filters(self) -> None:
        """Test get_filters with multiple filters."""
        specs = [
            {"id": "status", "label": "Status", "options": ["A"]},
            {"id": "type", "label": "Type", "options": ["X"]},
            {"id": "category", "label": "Category", "options": ["1"]},
        ]
        filter_set = FilterSet(specs)
        filter_set.init([])

        result = filter_set.get_filters()

        assert len(result) == 3
        ids = [f["id"] for f in result]
        assert ids == ["status", "type", "category"]

    def test_init_from_objects_without_options(self) -> None:
        """Test init extracts options from objects when not in spec."""

        @dataclass
        class Item:
            status: str

        specs = [{"id": "status", "label": "Status"}]  # No options in spec
        objects = [Item(status="Active"), Item(status="Inactive")]
        filter_set = FilterSet(specs)

        filter_set.init(objects)

        result = filter_set.get_filters()
        assert len(result[0]["options"]) == 2


class TestSorter:
    """Test suite for Sorter class."""

    def test_init_creates_options_with_sort_prefix(self) -> None:
        """Test Sorter creates options with sort: prefix."""
        options = [("date", "Date"), ("name", "Name"), ("score", "Score")]

        sorter = Sorter(options)

        assert len(sorter.options) == 3
        assert {"id": "sort:date", "label": "Date"} in sorter.options
        assert {"id": "sort:name", "label": "Name"} in sorter.options
        assert {"id": "sort:score", "label": "Score"} in sorter.options

    def test_init_with_empty_options(self) -> None:
        """Test Sorter with empty options."""
        sorter = Sorter([])

        assert sorter.options == []

    def test_current_with_session_using_app_context(self, app) -> None:
        """Test current property with Flask session in app context."""
        options = [("date", "Date"), ("name", "Name")]
        sorter = Sorter(options)

        with app.test_request_context():
            # Test default behavior (no session value set)
            result = sorter.current
            assert result == "Date"

            # Test with "name" set in session
            session["wire:sort-order"] = "name"
            result = sorter.current
            assert result == "Name"

            # Test with unknown value
            session["wire:sort-order"] = "unknown"
            result = sorter.current
            assert result == "Date (default)"
