# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC select widget field classes."""

from __future__ import annotations

import pytest
from typeguard import TypeCheckError
from wtforms import Form

from app.modules.kyc.lib.dual_select_multi import (
    DualSelectField,
    convert_dual_choices_js,
)
from app.modules.kyc.lib.select_multi_simple_free import (
    SelectMultiSimpleFreeField,
)
from app.modules.kyc.lib.select_one import (
    SelectOneField,
    convert_to_tom_choices_js,
    convert_to_tom_optgroups_js,
)
from app.modules.kyc.lib.select_one_free import (
    SelectOneFreeField,
    _dict_to_group_tom_choices,
    convert_to_tom_choices_js as convert_to_tom_choices_js_free,
    convert_to_tom_optgroups_js as convert_to_tom_optgroups_js_free,
)


class TestFormSelectOne(Form):
    """Test form for select one field."""

    category = SelectOneField(
        label="Category",
        choices=[("cat1", "Category 1"), ("cat2", "Category 2")],
    )
    category_readonly = SelectOneField(
        label="Category",
        choices=[("cat1", "Category 1")],
        readonly=True,
    )
    category_grouped = SelectOneField(
        label="Category",
        choices={
            "Group A": ["item1", "item2"],
            "Group B": ["item3"],
        },
    )


class TestFormSelectOneFree(Form):
    """Test form for select one free field."""

    tag = SelectOneFreeField(
        label="Tag",
        choices=[("tag1", "Tag 1"), ("tag2", "Tag 2")],
    )
    tag_readonly = SelectOneFreeField(
        label="Tag",
        choices=[("tag1", "Tag 1")],
        readonly=True,
    )


class TestFormSelectMultiFree(Form):
    """Test form for select multi simple free field."""

    tags = SelectMultiSimpleFreeField(
        label="Tags",
        choices=[("tag1", "Tag 1"), ("tag2", "Tag 2")],
    )
    tags_readonly = SelectMultiSimpleFreeField(
        label="Tags",
        choices=[("tag1", "Tag 1")],
        readonly=True,
    )


def test_convert_to_tom_choices_js_list():
    """Test converting list choices to Tom Select format."""
    choices = [("val1", "Label 1"), ("val2", "Label 2")]
    result = convert_to_tom_choices_js(choices)

    assert len(result) == 2
    assert result[0] == {"value": "val1", "label": "Label 1"}
    assert result[1] == {"value": "val2", "label": "Label 2"}


def test_convert_to_tom_choices_js_dict():
    """Test converting dict choices to Tom Select format."""
    choices = {
        "Group1": ["item1", "item2"],
        "Group2": ["item3"],
    }
    result = convert_to_tom_choices_js(choices)

    assert len(result) == 3
    assert result[0]["optgroup"] == "Group1"
    assert result[0]["value"] == "item1"
    assert result[0]["label"] == "item1"


def test_convert_to_tom_choices_js_invalid():
    """Test that invalid type raises TypeError."""
    with pytest.raises((TypeError, TypeCheckError)):
        convert_to_tom_choices_js("invalid")


def test_convert_to_tom_optgroups_js_list():
    """Test converting list to optgroups returns empty."""
    choices = [("val1", "Label 1")]
    result = convert_to_tom_optgroups_js(choices)
    assert result == []


def test_convert_to_tom_optgroups_js_dict():
    """Test converting dict to optgroups."""
    choices = {"Group A": ["item1"], "Group B": ["item2"]}
    result = convert_to_tom_optgroups_js(choices)

    assert len(result) == 2
    assert result[0] == {"value": "Group A", "label": "Group A"}
    assert result[1] == {"value": "Group B", "label": "Group B"}


def test_convert_to_tom_optgroups_js_invalid():
    """Test that invalid type raises TypeError."""
    with pytest.raises((TypeError, TypeCheckError)):
        convert_to_tom_optgroups_js("invalid")


def test_select_one_field_init():
    """Test SelectOneField initialization."""
    form = TestFormSelectOne()

    assert form.category.name == "category"
    assert form.category.label.text == "Category"
    assert not form.category.lock
    assert not form.category.multiple
    assert not form.category.create

    # Test readonly
    assert form.category_readonly.lock


def test_select_one_field_get_data():
    """Test SelectOneField get_data method."""
    form = TestFormSelectOne(data={"category": "cat1"})
    assert form.category.get_data() == repr("cat1")

    # Test with None
    form = TestFormSelectOne(data={"category": None})
    assert form.category.get_data() == repr("")


def test_select_one_field_get_tom_choices_for_js():
    """Test SelectOneField get_tom_choices_for_js method."""
    form = TestFormSelectOne()
    result = form.category.get_tom_choices_for_js()

    assert len(result) == 2
    assert result[0] == {"value": "cat1", "label": "Category 1"}
    assert result[1] == {"value": "cat2", "label": "Category 2"}


def test_select_one_field_get_tom_optgroups_for_js():
    """Test SelectOneField get_tom_optgroups_for_js method."""
    form = TestFormSelectOne()

    # With list choices, should return empty
    result = form.category.get_tom_optgroups_for_js()
    assert result == []

    # With grouped choices
    result = form.category_grouped.get_tom_optgroups_for_js()
    assert len(result) == 2
    assert {"value": "Group A", "label": "Group A"} in result
    assert {"value": "Group B", "label": "Group B"} in result


def test_select_one_free_field_init():
    """Test SelectOneFreeField initialization."""
    form = TestFormSelectOneFree()

    assert form.tag.name == "tag"
    assert form.tag.label.text == "Tag"
    assert not form.tag.lock
    assert not form.tag.multiple
    assert form.tag.create  # Should allow creation

    # Test readonly
    assert form.tag_readonly.lock


def test_select_one_free_field_get_data():
    """Test SelectOneFreeField get_data method."""
    form = TestFormSelectOneFree(data={"tag": "tag1"})
    assert form.tag.get_data() == repr("tag1")

    # Test with None
    form = TestFormSelectOneFree(data={"tag": None})
    assert form.tag.get_data() == repr("")


def test_select_one_free_field_get_tom_choices_for_js():
    """Test SelectOneFreeField get_tom_choices_for_js method."""
    form = TestFormSelectOneFree()
    result = form.tag.get_tom_choices_for_js()

    assert len(result) == 2
    assert result[0] == {"value": "tag1", "label": "Tag 1"}
    assert result[1] == {"value": "tag2", "label": "Tag 2"}


def test_select_multi_simple_free_field_init():
    """Test SelectMultiSimpleFreeField initialization."""
    form = TestFormSelectMultiFree()

    assert form.tags.name == "tags"
    assert form.tags.label.text == "Tags"
    assert not form.tags.lock
    assert form.tags.multiple
    assert form.tags.create  # Should allow creation

    # Test readonly
    assert form.tags_readonly.lock


def test_select_multi_simple_free_field_get_data():
    """Test SelectMultiSimpleFreeField get_data method."""
    form = TestFormSelectMultiFree(data={"tags": ["tag1", "tag2"]})
    result = form.tags.get_data()
    assert result == ["tag1", "tag2"]

    # Test with None
    form = TestFormSelectMultiFree(data={"tags": None})
    assert form.tags.get_data() == []


def test_select_multi_simple_free_field_get_tom_choices_for_js():
    """Test SelectMultiSimpleFreeField get_tom_choices_for_js method."""
    form = TestFormSelectMultiFree()
    result = form.tags.get_tom_choices_for_js()

    assert len(result) == 2
    assert result[0] == {"value": "tag1", "label": "Tag 1"}
    assert result[1] == {"value": "tag2", "label": "Tag 2"}


# =============================================================================
# Tests for dual_select_multi.py
# =============================================================================


class TestConvertDualChoicesJs:
    """Test suite for convert_dual_choices_js function."""

    def test_converts_basic_choices(self) -> None:
        """Test converting basic dual choices structure."""
        choices = {
            "field1": [("val1", "Label 1"), ("val2", "Label 2")],
            "field2": {
                "Group1": [("g1_v1", "G1 Label 1")],
                "Group2": [("g2_v1", "G2 Label 1"), ("g2_v2", "G2 Label 2")],
            },
        }
        result = convert_dual_choices_js(choices)

        assert "field1" in result
        assert "field2" in result
        assert len(result["field1"]) == 2
        assert result["field1"][0] == {"value": "val1", "label": "Label 1"}
        assert result["field1"][1] == {"value": "val2", "label": "Label 2"}

    def test_converts_field2_values(self) -> None:
        """Test field2 conversion flattens groups."""
        choices = {
            "field1": [("v1", "V1")],
            "field2": {
                "A": [("a1", "A1"), ("a2", "A2")],
                "B": [("b1", "B1")],
            },
        }
        result = convert_dual_choices_js(choices)

        # Should flatten all values from all groups
        assert len(result["field2"]) == 3
        values = [item["value"] for item in result["field2"]]
        assert "a1" in values
        assert "a2" in values
        assert "b1" in values

    def test_handles_empty_groups(self) -> None:
        """Test handling empty groups in field2."""
        choices = {
            "field1": [("v1", "V1")],
            "field2": {
                "Empty": [],
                "Filled": [("f1", "F1")],
            },
        }
        result = convert_dual_choices_js(choices)

        assert len(result["field2"]) == 1
        assert result["field2"][0] == {"value": "f1", "label": "F1"}


class TestFormDualSelect(Form):
    """Test form for dual select field."""

    selector = DualSelectField(
        label="Main Category",
        choices={
            "field1": [("cat1", "Category 1"), ("cat2", "Category 2")],
            "field2": {
                "cat1": [("sub1", "Sub 1"), ("sub2", "Sub 2")],
                "cat2": [("sub3", "Sub 3")],
            },
        },
        id2="subcategory",
        name2="subcategory",
        label2="Sub Category",
    )
    selector_readonly = DualSelectField(
        label="Readonly",
        choices={
            "field1": [("x", "X")],
            "field2": {"x": [("y", "Y")]},
        },
        readonly=True,
    )


class TestDualSelectFieldInit:
    """Test suite for DualSelectField initialization."""

    def test_basic_initialization(self) -> None:
        """Test DualSelectField basic init."""
        form = TestFormDualSelect()

        assert form.selector.name == "selector"
        assert form.selector.label.text == "Main Category"
        assert form.selector.id2 == "subcategory"
        assert form.selector.name2 == "subcategory"
        assert form.selector.label2 == "Sub Category"

    def test_multiple_is_true(self) -> None:
        """Test DualSelectField sets multiple=True."""
        form = TestFormDualSelect()
        assert form.selector.multiple is True

    def test_create_is_false(self) -> None:
        """Test DualSelectField sets create=False."""
        form = TestFormDualSelect()
        assert form.selector.create is False

    def test_double_select_is_true(self) -> None:
        """Test DualSelectField has double_select=True."""
        form = TestFormDualSelect()
        assert form.selector.double_select is True

    def test_lock_from_readonly(self) -> None:
        """Test lock is set from readonly kwarg."""
        form = TestFormDualSelect()

        assert form.selector.lock is False
        assert form.selector_readonly.lock is True


class TestDualSelectFieldGetData:
    """Test suite for DualSelectField get_data methods."""

    def test_get_data_with_values(self) -> None:
        """Test get_data returns repr of data."""
        form = TestFormDualSelect(data={"selector": ["cat1", "cat2"]})
        result = form.selector.get_data()

        assert result == repr(["cat1", "cat2"])

    def test_get_data_with_none(self) -> None:
        """Test get_data returns empty list repr when None."""
        form = TestFormDualSelect(data={"selector": None})
        result = form.selector.get_data()

        assert result == repr([])

    def test_get_data2_with_default(self) -> None:
        """Test get_data2 returns empty string repr when default."""
        form = TestFormDualSelect()
        result = form.selector.get_data2()

        # data2 defaults to empty string
        assert result == repr("")


class TestDualSelectFieldChoicesForJs:
    """Test suite for DualSelectField get_dual_tom_choices_for_js."""

    def test_returns_converted_choices(self) -> None:
        """Test get_dual_tom_choices_for_js returns converted structure."""
        form = TestFormDualSelect()
        result = form.selector.get_dual_tom_choices_for_js()

        assert "field1" in result
        assert "field2" in result
        assert len(result["field1"]) == 2
        assert result["field1"][0] == {"value": "cat1", "label": "Category 1"}


# =============================================================================
# Additional tests for select_one_free.py
# =============================================================================


class TestConvertToTomChoicesJsFree:
    """Test suite for select_one_free convert_to_tom_choices_js."""

    def test_converts_list_of_tuples(self) -> None:
        """Test converting list of tuples."""
        choices = [("v1", "Label 1"), ("v2", "Label 2")]
        result = convert_to_tom_choices_js_free(choices)

        assert len(result) == 2
        assert result[0] == {"value": "v1", "label": "Label 1"}

    def test_raises_type_error_for_non_list(self) -> None:
        """Test raises TypeError for non-list input."""
        with pytest.raises((TypeError, TypeCheckError)):
            convert_to_tom_choices_js_free("invalid")

    def test_raises_type_error_for_dict(self) -> None:
        """Test raises TypeError for dict input."""
        with pytest.raises((TypeError, TypeCheckError)):
            convert_to_tom_choices_js_free({"key": "value"})


class TestConvertToTomOptgroupsJsFree:
    """Test suite for select_one_free convert_to_tom_optgroups_js."""

    def test_returns_empty_for_list(self) -> None:
        """Test returns empty list for list input."""
        result = convert_to_tom_optgroups_js_free([("v1", "L1")])
        assert result == []

    def test_returns_optgroups_for_dict(self) -> None:
        """Test returns optgroups for dict input."""
        choices = {"GroupA": ["item1"], "GroupB": ["item2"]}
        result = convert_to_tom_optgroups_js_free(choices)

        assert len(result) == 2
        assert {"value": "GroupA", "label": "GroupA"} in result

    def test_raises_type_error_for_invalid(self) -> None:
        """Test raises TypeError for invalid input."""
        with pytest.raises((TypeError, TypeCheckError)):
            convert_to_tom_optgroups_js_free("invalid")


class TestDictToGroupTomChoices:
    """Test suite for _dict_to_group_tom_choices function."""

    def test_converts_dict_to_grouped_choices(self) -> None:
        """Test converting dict to grouped choices format."""
        choices = {
            "Group1": ["item1", "item2"],
            "Group2": ["item3"],
        }
        result = _dict_to_group_tom_choices(choices)

        assert len(result) == 3
        assert result[0] == {"optgroup": "Group1", "value": "item1", "label": "item1"}
        assert result[1] == {"optgroup": "Group1", "value": "item2", "label": "item2"}
        assert result[2] == {"optgroup": "Group2", "value": "item3", "label": "item3"}

    def test_handles_empty_groups(self) -> None:
        """Test handling empty groups."""
        choices = {
            "Empty": [],
            "Filled": ["item1"],
        }
        result = _dict_to_group_tom_choices(choices)

        assert len(result) == 1
        assert result[0] == {"optgroup": "Filled", "value": "item1", "label": "item1"}

    def test_preserves_group_order(self) -> None:
        """Test groups are processed in order."""
        choices = {
            "First": ["a"],
            "Second": ["b"],
        }
        result = _dict_to_group_tom_choices(choices)

        assert result[0]["optgroup"] == "First"
        assert result[1]["optgroup"] == "Second"


class TestSelectOneFreeFieldGetTomOptgroupsForJs:
    """Test suite for SelectOneFreeField get_tom_optgroups_for_js."""

    def test_returns_empty_for_list_choices(self) -> None:
        """Test returns empty for list choices."""
        form = TestFormSelectOneFree()
        result = form.tag.get_tom_optgroups_for_js()

        assert result == []
