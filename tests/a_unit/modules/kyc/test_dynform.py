# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC dynamic form creation."""

from __future__ import annotations

from app.modules.kyc.dynform import (
    TAG_AREA300_SIZE,
    TAG_AREA_SIZE,
    TAG_FREE_ELEMENT,
    TAG_MANDATORY,
    TAG_MANY_CHOICES,
    TAG_PHOTO_FORMAT,
    TAG_PUBLIC,
    _filter_mandatory_label,
    _filter_mandatory_label_free,
    _filter_mandatory_validator,
    _filter_many_choices,
    _filter_max_textarea300_size,
    _filter_max_textarea_size,
    _filter_photo_format,
    _filter_public_info,
    _get_part,
    _is_required,
    custom_bool_field,
    custom_bool_link_field,
    custom_email_field,
    custom_int_field,
    custom_password_field,
    custom_photo_field,
    custom_postcode_field,
    custom_string_field,
    custom_tel_field,
    custom_textarea300_field,
    custom_textarea_field,
    custom_url_field,
)
from app.modules.kyc.survey_dataclass import SurveyField


def test_filter_public_info():
    """Test _filter_public_info function."""
    # With public=True
    result = _filter_public_info("Test description", True)
    assert result == f"Test description {TAG_PUBLIC}"

    # With public=False
    result = _filter_public_info("Test description", False)
    assert result == "Test description"


def test_filter_mandatory_label():
    """Test _filter_mandatory_label function."""
    # With mandatory code
    result = _filter_mandatory_label("Test field", "M")
    assert result == f"Test field {TAG_MANDATORY}"

    # Without mandatory code
    result = _filter_mandatory_label("Test field", "O")
    assert result == "Test field"


def test_filter_many_choices():
    """Test _filter_many_choices function."""
    result = _filter_many_choices("Select options")
    assert result == f"Select options {TAG_MANY_CHOICES}"


def test_filter_max_textarea_size():
    """Test _filter_max_textarea_size function."""
    result = _filter_max_textarea_size("Enter text")
    assert result == f"Enter text {TAG_AREA_SIZE}"


def test_filter_max_textarea300_size():
    """Test _filter_max_textarea300_size function."""
    result = _filter_max_textarea300_size("Enter short text")
    assert result == f"Enter short text {TAG_AREA300_SIZE}"


def test_filter_photo_format():
    """Test _filter_photo_format function."""
    result = _filter_photo_format("Upload photo")
    assert result == f"Upload photo {TAG_PHOTO_FORMAT}"


def test_filter_mandatory_label_free():
    """Test _filter_mandatory_label_free function."""
    # With mandatory code
    result = _filter_mandatory_label_free("Add item", "M")
    assert TAG_FREE_ELEMENT in result
    assert TAG_MANDATORY in result

    # Without mandatory code
    result = _filter_mandatory_label_free("Add item", "O")
    assert TAG_FREE_ELEMENT in result
    assert TAG_MANDATORY not in result


def test_is_required():
    """Test _is_required function."""
    assert _is_required("M") is True
    assert _is_required("O") is False
    assert _is_required("") is False


def test_filter_mandatory_validator():
    """Test _filter_mandatory_validator function."""
    from wtforms import validators

    # Mandatory field
    result = _filter_mandatory_validator("M")
    assert len(result) == 1
    assert isinstance(result[0], validators.InputRequired)

    # Optional field
    result = _filter_mandatory_validator("O")
    assert len(result) == 1
    assert isinstance(result[0], validators.Optional)


def test_get_part():
    """Test _get_part function."""
    parts = ["part1", "part2", "part3"]

    # Valid indices
    assert _get_part(parts, 0) == "part1"
    assert _get_part(parts, 1) == "part2"
    assert _get_part(parts, 2) == "part3"

    # Index out of range
    assert _get_part(parts, 3) == ""
    assert _get_part(parts, 10) == ""

    # Test with whitespace
    parts_with_space = ["  part1  ", "  part2  "]
    assert _get_part(parts_with_space, 0) == "part1"
    assert _get_part(parts_with_space, 1) == "part2"


def test_custom_bool_field():
    """Test custom_bool_field function."""
    field = SurveyField(
        id="test_id",
        name="test_bool",
        description="Test boolean field",
        upper_message="Test message",
    )

    # Basic field - returns UnboundField
    result = custom_bool_field(field, "M")
    assert result is not None

    # Readonly field
    result = custom_bool_field(field, "M", readonly=True)
    assert result is not None


def test_custom_bool_link_field():
    """Test custom_bool_link_field function."""
    field = SurveyField(
        id="test_id",
        name="test_link",
        description="Accept terms; https://example.com; Terms",
        upper_message="Test message",
    )

    result = custom_bool_link_field(field, "M")
    assert result is not None


def test_custom_string_field():
    """Test custom_string_field function."""
    field = SurveyField(
        id="test_id",
        name="test_string",
        description="Test string field",
        public_maxi=True,
        upper_message="Test message",
    )

    # Mandatory field
    result = custom_string_field(field, "M")
    assert result is not None

    # Readonly field
    result = custom_string_field(field, "M", readonly=True)
    assert result is not None


def test_custom_int_field():
    """Test custom_int_field function."""
    field = SurveyField(
        id="test_id",
        name="test_int",
        description="Test integer field",
        public_maxi=False,
        upper_message="Test message",
    )

    result = custom_int_field(field, "M")
    assert result is not None


def test_custom_photo_field():
    """Test custom_photo_field function."""
    field = SurveyField(
        id="test_id",
        name="test_photo",
        description="Upload photo",
        public_maxi=True,
        upper_message="Test message",
    )

    result = custom_photo_field(field, "M")
    assert result is not None

    # Optional photo
    result = custom_photo_field(field, "O")
    assert result is not None


def test_custom_email_field():
    """Test custom_email_field function."""
    field = SurveyField(
        id="test_id",
        name="test_email",
        description="Email address",
        public_maxi=True,
        upper_message="Test message",
    )

    result = custom_email_field(field, "M")
    assert result is not None


def test_custom_tel_field():
    """Test custom_tel_field function."""
    field = SurveyField(
        id="test_id",
        name="test_tel",
        description="Phone number",
        public_maxi=False,
        upper_message="Test message",
    )

    result = custom_tel_field(field, "M")
    assert result is not None


def test_custom_password_field():
    """Test custom_password_field function."""
    field = SurveyField(
        id="test_id",
        name="test_password",
        description="Password",
        public_maxi=False,
        upper_message="Test message",
    )

    result = custom_password_field(field, "M")
    assert result is not None


def test_custom_postcode_field():
    """Test custom_postcode_field function."""
    field = SurveyField(
        id="test_id",
        name="test_postcode",
        description="Postal code",
        public_maxi=True,
        upper_message="Test message",
    )

    result = custom_postcode_field(field, "M")
    assert result is not None


def test_custom_url_field():
    """Test custom_url_field function."""
    field = SurveyField(
        id="test_id",
        name="test_url",
        description="Website URL",
        public_maxi=True,
        upper_message="Test message",
    )

    result = custom_url_field(field, "M")
    assert result is not None


def test_custom_textarea_field():
    """Test custom_textarea_field function."""
    field = SurveyField(
        id="test_id",
        name="test_textarea",
        description="Long text",
        public_maxi=True,
        upper_message="Test message",
    )

    result = custom_textarea_field(field, "M")
    assert result is not None


def test_custom_textarea300_field():
    """Test custom_textarea300_field function."""
    field = SurveyField(
        id="test_id",
        name="test_textarea300",
        description="Short text",
        public_maxi=False,
        upper_message="Test message",
    )

    result = custom_textarea300_field(field, "M")
    assert result is not None


def test_field_creation_functions_callable():
    """Test that all field creation functions are callable and return fields."""
    field = SurveyField(
        id="test_id",
        name="test_field",
        description="Test",
        public_maxi=False,
        upper_message="",
    )

    # Test all field creation functions return non-None
    assert custom_bool_field(field, "M") is not None
    assert custom_bool_link_field(field, "M") is not None
    assert custom_string_field(field, "M") is not None
    assert custom_int_field(field, "M") is not None
    assert custom_photo_field(field, "M") is not None
    assert custom_email_field(field, "M") is not None
    assert custom_tel_field(field, "M") is not None
    assert custom_password_field(field, "M") is not None
    assert custom_postcode_field(field, "M") is not None
    assert custom_url_field(field, "M") is not None
    assert custom_textarea_field(field, "M") is not None
    assert custom_textarea300_field(field, "M") is not None
