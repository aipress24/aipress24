# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC widget field classes."""

from __future__ import annotations

import base64

import pytest
from wtforms import Form

from app.modules.kyc.lib.country_select import (
    CountrySelectField,
    convert_country_to_tom_choices_js,
)
from app.modules.kyc.lib.select_multi_simple import (
    SelectMultiSimpleField,
    convert_to_tom_choices_js,
)
from app.modules.kyc.lib.valid_image import ValidImageField


class TestFormCountry(Form):
    """Test form for country select field."""

    country = CountrySelectField(
        label="Country",
        choices=[("FR", "France"), ("US", "United States")],
    )
    country_readonly = CountrySelectField(
        label="Country",
        choices=[("FR", "France"), ("US", "United States")],
        readonly=True,
    )
    country_with_extra = CountrySelectField(
        label="Country",
        choices=[("FR", "France")],
        id2="region",
        name2="region",
        label2="Region",
    )


class TestFormSelectMulti(Form):
    """Test form for select multi simple field."""

    tags = SelectMultiSimpleField(
        label="Tags",
        choices=[("tag1", "Tag 1"), ("tag2", "Tag 2"), ("tag3", "Tag 3")],
    )
    tags_readonly = SelectMultiSimpleField(
        label="Tags",
        choices=[("tag1", "Tag 1")],
        readonly=True,
    )


class TestFormImage(Form):
    """Test form for image field."""

    logo = ValidImageField(label="Logo")
    logo_required = ValidImageField(label="Logo", is_required=True)
    logo_readonly = ValidImageField(label="Logo", readonly=True)
    logo_custom = ValidImageField(
        label="Logo",
        max_image_size=1024,
    )


def test_convert_country_to_tom_choices_js():
    """Test converting country choices to Tom Select format."""
    choices = [("FR", "France"), ("US", "United States"), ("DE", "Germany")]
    result = convert_country_to_tom_choices_js(choices)

    assert len(result) == 3
    assert result[0] == {"value": "FR", "label": "France"}
    assert result[1] == {"value": "US", "label": "United States"}
    assert result[2] == {"value": "DE", "label": "Germany"}


def test_convert_to_tom_choices_js_with_list():
    """Test converting list choices to Tom Select format."""
    choices = [("val1", "Label 1"), ("val2", "Label 2")]
    result = convert_to_tom_choices_js(choices)

    assert len(result) == 2
    assert result[0] == {"value": "val1", "label": "Label 1"}
    assert result[1] == {"value": "val2", "label": "Label 2"}


def test_convert_to_tom_choices_js_with_dict():
    """Test converting dict choices to Tom Select format."""
    choices = {
        "Group1": ["item1", "item2"],
        "Group2": ["item3"],
    }
    result = convert_to_tom_choices_js(choices)

    assert len(result) == 3
    assert result[0] == {"optgroup": "Group1", "value": "item1", "label": "item1"}
    assert result[1] == {"optgroup": "Group1", "value": "item2", "label": "item2"}
    assert result[2] == {"optgroup": "Group2", "value": "item3", "label": "item3"}


def test_convert_to_tom_choices_js_with_invalid_type():
    """Test that invalid type raises TypeError."""
    with pytest.raises(TypeError):
        convert_to_tom_choices_js("invalid")


def test_country_select_field_init():
    """Test CountrySelectField initialization."""
    form = TestFormCountry()

    assert form.country.name == "country"
    assert form.country.label.text == "Country"
    assert not form.country.lock
    assert not form.country.multiple
    assert not form.country.create
    assert form.country.double_select

    # Test readonly
    assert form.country_readonly.lock


def test_country_select_field_with_extra_params():
    """Test CountrySelectField with id2, name2, label2."""
    form = TestFormCountry()

    assert form.country_with_extra.id2 == "region"
    assert form.country_with_extra.name2 == "region"
    assert form.country_with_extra.label2 == "Region"


def test_country_select_field_get_data():
    """Test CountrySelectField get_data method."""
    form = TestFormCountry(data={"country": "FR"})
    assert form.country.get_data() == repr("FR")

    # Test with None
    form = TestFormCountry(data={"country": None})
    assert form.country.get_data() == repr("")


def test_country_select_field_get_data2():
    """Test CountrySelectField get_data2 method."""
    form = TestFormCountry()

    # With data2 set
    form.country.data2 = "test_region"
    assert form.country.get_data2() == repr("test_region")

    # With None
    form.country.data2 = None
    assert form.country.get_data2() == repr([])


def test_country_select_field_get_tom_choices_for_js():
    """Test CountrySelectField get_tom_choices_for_js method."""
    form = TestFormCountry()
    result = form.country.get_tom_choices_for_js()

    assert len(result) == 2
    assert result[0] == {"value": "FR", "label": "France"}
    assert result[1] == {"value": "US", "label": "United States"}


def test_select_multi_simple_field_init():
    """Test SelectMultiSimpleField initialization."""
    form = TestFormSelectMulti()

    assert form.tags.name == "tags"
    assert form.tags.label.text == "Tags"
    assert not form.tags.lock
    assert form.tags.multiple
    assert not form.tags.create

    # Test readonly
    assert form.tags_readonly.lock


def test_select_multi_simple_field_get_data():
    """Test SelectMultiSimpleField get_data method."""
    form = TestFormSelectMulti(data={"tags": ["tag1", "tag2"]})
    result = form.tags.get_data()

    assert result == ["tag1", "tag2"]

    # Test with None
    form = TestFormSelectMulti(data={"tags": None})
    assert form.tags.get_data() == []


def test_select_multi_simple_field_get_tom_choices_for_js():
    """Test SelectMultiSimpleField get_tom_choices_for_js method."""
    form = TestFormSelectMulti()
    result = form.tags.get_tom_choices_for_js()

    assert len(result) == 3
    assert result[0] == {"value": "tag1", "label": "Tag 1"}
    assert result[1] == {"value": "tag2", "label": "Tag 2"}
    assert result[2] == {"value": "tag3", "label": "Tag 3"}


def test_valid_image_field_init():
    """Test ValidImageField initialization."""
    form = TestFormImage()

    assert form.logo.name == "logo"
    assert form.logo.label.text == "Logo"
    assert not form.logo.readonly
    assert not form.logo.is_required
    assert not form.logo.multiple
    assert form.logo.max_image_size == 2048

    # Test with is_required
    assert form.logo_required.is_required

    # Test with readonly
    assert form.logo_readonly.readonly

    # Test with custom max_image_size
    assert form.logo_custom.max_image_size == 1024


def test_valid_image_field_load_data():
    """Test ValidImageField load_data method."""
    form = TestFormImage()

    # Test loading data
    test_data = b"test image data"
    form.logo.load_data(test_data, "test.jpg")

    assert form.logo.data == test_data
    assert form.logo.data_b64 == base64.standard_b64encode(test_data)
    assert form.logo.preload_filename == "test.jpg"
    assert form.logo.preload_filesize == len(test_data)


def test_valid_image_field_preloaded_image():
    """Test ValidImageField preloaded_image method."""
    form = TestFormImage()

    test_data = b"test image data"
    form.logo.load_data(test_data, "test.jpg")

    result = form.logo.preloaded_image()
    assert result == base64.standard_b64encode(test_data).decode()


def test_valid_image_field_id_methods():
    """Test ValidImageField id-related methods."""
    form = TestFormImage()

    # These methods generate IDs for preload fields
    assert form.logo.id_preload_name() == "logo_preload_name"
    assert form.logo.name_preload_name() == "logo_preload_name"
    assert form.logo.id_preload_b64() == "logo_preload_b64"
    assert form.logo.name_preload_b64() == "logo_preload_b64"
