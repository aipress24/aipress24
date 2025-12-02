# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for swork/components/selector.py."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.swork.components.selector import Selector


@dataclass
class StubFilter:
    """Stub filter object for testing Selector component."""

    label: str
    id: str
    options: list


class TestSelectorComponent:
    """Test suite for Selector component."""

    def test_selector_initializes_with_id(self):
        """Test that Selector can be initialized with an ID."""
        selector = Selector(id="test-id")
        assert selector._id == "test-id"

    def test_selector_initializes_with_generated_id(self):
        """Test that Selector generates a UUID when no ID is provided."""
        selector = Selector()
        assert selector._id is not None
        assert len(selector._id) == 32  # UUID hex length

    def test_selector_mount_sets_label(self):
        """Test that mount sets label from filter."""
        selector = Selector()
        stub_filter = StubFilter(
            label="Category",
            id="category-filter",
            options=[("all", "All"), ("news", "News")],
        )

        selector.mount(parent=None, filter=stub_filter)

        assert selector.label == "Category"

    def test_selector_mount_sets_name(self):
        """Test that mount sets name from filter.id."""
        selector = Selector()
        stub_filter = StubFilter(
            label="Type",
            id="type-selector",
            options=[("a", "Option A")],
        )

        selector.mount(parent=None, filter=stub_filter)

        assert selector.name == "type-selector"

    def test_selector_mount_sets_options(self):
        """Test that mount sets options from filter."""
        selector = Selector()
        options = [
            ("value1", "Label 1"),
            ("value2", "Label 2"),
            ("value3", "Label 3"),
        ]
        stub_filter = StubFilter(label="Test", id="test", options=options)

        selector.mount(parent=None, filter=stub_filter)

        assert selector.options == options
        assert len(selector.options) == 3

    def test_selector_mount_with_empty_options(self):
        """Test that mount handles empty options list."""
        selector = Selector()
        stub_filter = StubFilter(label="Empty", id="empty", options=[])

        selector.mount(parent=None, filter=stub_filter)

        assert selector.options == []

    def test_selector_get_name_returns_kebab_case(self):
        """Test that _get_name returns kebab-case class name."""
        name = Selector._get_name()
        assert name == "selector"
