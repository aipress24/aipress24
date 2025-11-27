# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/lib utility functions."""

from __future__ import annotations

import pytest

from app.modules.kyc.lib.dual_select_multi import convert_dual_choices_js
from app.modules.kyc.lib.select_multi_optgroup import (
    _dict_to_group_tom_choices,
    convert_to_tom_choices_js,
    convert_to_tom_optgroups_js,
)


class TestConvertToTomChoicesJs:
    """Test suite for convert_to_tom_choices_js function."""

    def test_converts_list_to_tom_format(self) -> None:
        """Test converting list of tuples to tom-select format."""
        choices = [("val1", "Label 1"), ("val2", "Label 2")]

        result = convert_to_tom_choices_js(choices)

        assert result == [
            {"value": "val1", "label": "Label 1"},
            {"value": "val2", "label": "Label 2"},
        ]

    def test_converts_empty_list(self) -> None:
        """Test converting empty list."""
        result = convert_to_tom_choices_js([])
        assert result == []

    def test_converts_dict_to_grouped_format(self) -> None:
        """Test converting dict to grouped tom-select format."""
        choices = {
            "Group A": ["Item 1", "Item 2"],
            "Group B": ["Item 3"],
        }

        result = convert_to_tom_choices_js(choices)

        assert {"optgroup": "Group A", "value": "Item 1", "label": "Item 1"} in result
        assert {"optgroup": "Group A", "value": "Item 2", "label": "Item 2"} in result
        assert {"optgroup": "Group B", "value": "Item 3", "label": "Item 3"} in result

    def test_raises_type_error_for_invalid_type(self) -> None:
        """Test raises TypeError for invalid input type."""
        with pytest.raises(TypeError):
            convert_to_tom_choices_js("invalid")  # type: ignore


class TestConvertToTomOptgroupsJs:
    """Test suite for convert_to_tom_optgroups_js function."""

    def test_returns_empty_for_list(self) -> None:
        """Test returns empty list for list input."""
        choices = [("val1", "Label 1")]
        result = convert_to_tom_optgroups_js(choices)
        assert result == []

    def test_converts_dict_keys_to_optgroups(self) -> None:
        """Test converts dict keys to optgroup format."""
        choices = {
            "Group A": ["Item 1"],
            "Group B": ["Item 2"],
        }

        result = convert_to_tom_optgroups_js(choices)

        assert {"value": "Group A", "label": "Group A"} in result
        assert {"value": "Group B", "label": "Group B"} in result

    def test_returns_empty_for_empty_dict(self) -> None:
        """Test returns empty list for empty dict."""
        result = convert_to_tom_optgroups_js({})
        assert result == []

    def test_raises_type_error_for_invalid_type(self) -> None:
        """Test raises TypeError for invalid input type."""
        with pytest.raises(TypeError):
            convert_to_tom_optgroups_js("invalid")  # type: ignore


class TestDictToGroupTomChoices:
    """Test suite for _dict_to_group_tom_choices function."""

    def test_converts_dict_to_grouped_choices(self) -> None:
        """Test converting dict to grouped choices."""
        choices = {
            "Category 1": ["Option A", "Option B"],
            "Category 2": ["Option C"],
        }

        result = _dict_to_group_tom_choices(choices)

        assert len(result) == 3
        assert {"optgroup": "Category 1", "value": "Option A", "label": "Option A"} in result
        assert {"optgroup": "Category 1", "value": "Option B", "label": "Option B"} in result
        assert {"optgroup": "Category 2", "value": "Option C", "label": "Option C"} in result

    def test_empty_dict_returns_empty_list(self) -> None:
        """Test empty dict returns empty list."""
        result = _dict_to_group_tom_choices({})
        assert result == []

    def test_empty_group_values(self) -> None:
        """Test group with empty values list."""
        choices = {"Empty Group": []}
        result = _dict_to_group_tom_choices(choices)
        assert result == []


class TestConvertDualChoicesJs:
    """Test suite for convert_dual_choices_js function."""

    def test_converts_dual_select_choices(self) -> None:
        """Test converting dual select choices format."""
        choices = {
            "field1": [("cat1", "Category 1"), ("cat2", "Category 2")],
            "field2": {
                "Category 1": [("cat1/opt1", "Category 1 / Option 1")],
                "Category 2": [("cat2/opt2", "Category 2 / Option 2")],
            },
        }

        result = convert_dual_choices_js(choices)

        assert "field1" in result
        assert "field2" in result
        assert {"value": "cat1", "label": "Category 1"} in result["field1"]
        assert {"value": "cat2", "label": "Category 2"} in result["field1"]
        assert {"value": "cat1/opt1", "label": "Category 1 / Option 1"} in result["field2"]
        assert {"value": "cat2/opt2", "label": "Category 2 / Option 2"} in result["field2"]

    def test_empty_choices(self) -> None:
        """Test with empty choices."""
        choices = {"field1": [], "field2": {}}

        result = convert_dual_choices_js(choices)

        assert result == {"field1": [], "field2": []}

    def test_multiple_options_per_category(self) -> None:
        """Test with multiple options per category."""
        choices = {
            "field1": [("cat1", "Category 1")],
            "field2": {
                "Category 1": [
                    ("cat1/opt1", "Option 1"),
                    ("cat1/opt2", "Option 2"),
                    ("cat1/opt3", "Option 3"),
                ],
            },
        }

        result = convert_dual_choices_js(choices)

        assert len(result["field2"]) == 3
