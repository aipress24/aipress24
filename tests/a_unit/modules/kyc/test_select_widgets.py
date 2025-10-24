# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC select widget field classes."""

from __future__ import annotations

import pytest
from wtforms import Form

from app.modules.kyc.lib.select_multi_simple_free import (
    SelectMultiSimpleFreeField,
)
from app.modules.kyc.lib.select_one import (
    SelectOneField,
    convert_to_tom_choices_js,
    convert_to_tom_optgroups_js,
)
from app.modules.kyc.lib.select_one_free import SelectOneFreeField


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
    with pytest.raises(TypeError):
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
    with pytest.raises(TypeError, match="choices must be a list or a dict"):
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
