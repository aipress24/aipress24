# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC dynamic form creation."""

from __future__ import annotations

from wtforms import BooleanField, IntegerField, StringField, TextAreaField, validators
from wtforms.fields.core import UnboundField

from app.modules.kyc.dynform import (
    TAG_AREA300_SIZE,
    TAG_AREA_SIZE,
    TAG_FREE_ELEMENT,
    TAG_MANDATORY,
    TAG_MANY_CHOICES,
    TAG_PHOTO_FORMAT,
    TAG_PUBLIC,
    _fake_ontology_ajax,
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
    custom_ajax_field,
    custom_bool_field,
    custom_bool_link_field,
    custom_country_field,
    custom_email_field,
    custom_int_field,
    custom_list_field,
    custom_list_free_field,
    custom_multi_field,
    custom_multi_free_field,
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


def test_filter_public_info() -> None:
    """Test _filter_public_info function."""
    # With public=True
    result = _filter_public_info("Test description", True)
    assert result == f"Test description {TAG_PUBLIC}"

    # With public=False
    result = _filter_public_info("Test description", False)
    assert result == "Test description"


def test_filter_mandatory_label() -> None:
    """Test _filter_mandatory_label function."""
    # With mandatory code
    result = _filter_mandatory_label("Test field", "M")
    assert result == f"Test field {TAG_MANDATORY}"

    # Without mandatory code
    result = _filter_mandatory_label("Test field", "O")
    assert result == "Test field"


def test_filter_many_choices() -> None:
    """Test _filter_many_choices function."""
    result = _filter_many_choices("Select options")
    assert result == f"Select options {TAG_MANY_CHOICES}"


def test_filter_max_textarea_size() -> None:
    """Test _filter_max_textarea_size function."""
    result = _filter_max_textarea_size("Enter text")
    assert result == f"Enter text {TAG_AREA_SIZE}"


def test_filter_max_textarea300_size() -> None:
    """Test _filter_max_textarea300_size function."""
    result = _filter_max_textarea300_size("Enter short text")
    assert result == f"Enter short text {TAG_AREA300_SIZE}"


def test_filter_photo_format() -> None:
    """Test _filter_photo_format function."""
    result = _filter_photo_format("Upload photo")
    assert result == f"Upload photo {TAG_PHOTO_FORMAT}"


def test_filter_mandatory_label_free() -> None:
    """Test _filter_mandatory_label_free function."""
    # With mandatory code
    result = _filter_mandatory_label_free("Add item", "M")
    assert TAG_FREE_ELEMENT in result
    assert TAG_MANDATORY in result

    # Without mandatory code
    result = _filter_mandatory_label_free("Add item", "O")
    assert TAG_FREE_ELEMENT in result
    assert TAG_MANDATORY not in result


def test_is_required() -> None:
    """Test _is_required function."""
    assert _is_required("M") is True
    assert _is_required("O") is False
    assert _is_required("") is False


def test_filter_mandatory_validator() -> None:
    """Test _filter_mandatory_validator function."""
    # Mandatory field
    result = _filter_mandatory_validator("M")
    assert len(result) == 1
    assert isinstance(result[0], validators.InputRequired)

    # Optional field
    result = _filter_mandatory_validator("O")
    assert len(result) == 1
    assert isinstance(result[0], validators.Optional)


def test_get_part() -> None:
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


class TestCustomBoolField:
    """Test custom_bool_field function."""

    def test_returns_boolean_field(self) -> None:
        """Test custom_bool_field returns a BooleanField."""
        field = SurveyField(
            id="test_id",
            name="test_bool",
            description="Test boolean field",
            upper_message="Test message",
        )

        result = custom_bool_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.field_class is BooleanField
        assert result.kwargs["id"] == "test_id"

    def test_sets_render_kw_with_kyc_type(self) -> None:
        """Test render_kw contains kyc_type='boolean'."""
        field = SurveyField(
            id="test_id",
            name="test_bool",
            description="Test boolean field",
            upper_message="Test message",
        )

        result = custom_bool_field(field, "M")

        assert result.kwargs["render_kw"]["kyc_type"] == "boolean"
        assert result.kwargs["render_kw"]["kyc_message"] == "Test message"

    def test_readonly_sets_disabled(self) -> None:
        """Test readonly=True adds disabled to render_kw."""
        field = SurveyField(
            id="test_id",
            name="test_bool",
            description="Test boolean field",
            upper_message="",
        )

        result = custom_bool_field(field, "M", readonly=True)

        assert "disabled" in result.kwargs["render_kw"]


class TestCustomBoolLinkField:
    """Test custom_bool_link_field function."""

    def test_parses_description_into_link(self) -> None:
        """Test description with semicolons is parsed into a link."""
        field = SurveyField(
            id="test_id",
            name="test_link",
            description="Accept terms; https://example.com; Terms",
            upper_message="",
        )

        result = custom_bool_link_field(field, "M")

        # Label should contain the link
        label = str(result.kwargs["label"])
        assert "Accept terms" in label
        assert 'href="https://example.com"' in label
        assert "Terms</a>" in label


class TestCustomStringField:
    """Test custom_string_field function."""

    def test_returns_string_field(self) -> None:
        """Test custom_string_field returns a StringField."""
        field = SurveyField(
            id="test_id",
            name="test_string",
            description="Test string field",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_string_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.field_class is StringField
        assert result.kwargs["id"] == "test_id"

    def test_mandatory_field_has_mandatory_marker_in_label(self) -> None:
        """Test mandatory field label contains TAG_MANDATORY."""
        field = SurveyField(
            id="test_id",
            name="test_string",
            description="Test field",
            public_maxi=False,
            upper_message="",
        )

        result = custom_string_field(field, "M")

        assert TAG_MANDATORY in result.kwargs["label"]

    def test_public_field_has_public_marker_in_label(self) -> None:
        """Test public field label contains TAG_PUBLIC."""
        field = SurveyField(
            id="test_id",
            name="test_string",
            description="Test field",
            public_maxi=True,
            upper_message="",
        )

        result = custom_string_field(field, "O")

        assert TAG_PUBLIC in result.kwargs["label"]

    def test_readonly_sets_readonly_in_render_kw(self) -> None:
        """Test readonly=True adds readonly to render_kw."""
        field = SurveyField(
            id="test_id",
            name="test_string",
            description="Test field",
            public_maxi=False,
            upper_message="",
        )

        result = custom_string_field(field, "M", readonly=True)

        assert result.kwargs["render_kw"]["readonly"] is True

    def test_sets_kyc_type_in_render_kw(self) -> None:
        """Test render_kw contains kyc_type='string'."""
        field = SurveyField(
            id="test_id",
            name="test_string",
            description="Test field",
            public_maxi=False,
            upper_message="",
        )

        result = custom_string_field(field, "M")

        assert result.kwargs["render_kw"]["kyc_type"] == "string"
        assert result.kwargs["render_kw"]["kyc_code"] == "M"


class TestCustomIntField:
    """Test custom_int_field function."""

    def test_returns_integer_field(self) -> None:
        """Test custom_int_field returns an IntegerField."""
        field = SurveyField(
            id="test_id",
            name="test_int",
            description="Test integer field",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_int_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.field_class is IntegerField
        assert result.kwargs["render_kw"]["kyc_type"] == "int"


class TestCustomPhotoField:
    """Test custom_photo_field function."""

    def test_label_contains_photo_format_tag(self) -> None:
        """Test photo field label contains format instructions."""
        field = SurveyField(
            id="test_id",
            name="test_photo",
            description="Upload photo",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_photo_field(field, "M")

        assert isinstance(result, UnboundField)
        assert TAG_PHOTO_FORMAT in result.kwargs["label"]

    def test_mandatory_photo_sets_is_required(self) -> None:
        """Test mandatory photo has is_required=True."""
        field = SurveyField(
            id="test_id",
            name="test_photo",
            description="Upload photo",
            public_maxi=False,
            upper_message="",
        )

        result = custom_photo_field(field, "M")

        assert result.kwargs["is_required"] is True

    def test_optional_photo_sets_is_required_false(self) -> None:
        """Test optional photo has is_required=False."""
        field = SurveyField(
            id="test_id",
            name="test_photo",
            description="Upload photo",
            public_maxi=False,
            upper_message="",
        )

        result = custom_photo_field(field, "O")

        assert result.kwargs["is_required"] is False


class TestCustomEmailField:
    """Test custom_email_field function."""

    def test_returns_field_with_email_kyc_type(self) -> None:
        """Test custom_email_field sets kyc_type='email'."""
        field = SurveyField(
            id="test_id",
            name="test_email",
            description="Email address",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_email_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.kwargs["render_kw"]["kyc_type"] == "email"


class TestCustomTelField:
    """Test custom_tel_field function."""

    def test_returns_field_with_tel_kyc_type(self) -> None:
        """Test custom_tel_field sets kyc_type='tel'."""
        field = SurveyField(
            id="test_id",
            name="test_tel",
            description="Phone number",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_tel_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.kwargs["render_kw"]["kyc_type"] == "tel"


class TestCustomPasswordField:
    """Test custom_password_field function."""

    def test_returns_field_with_password_kyc_type(self) -> None:
        """Test custom_password_field sets kyc_type='password'."""
        field = SurveyField(
            id="test_id",
            name="test_password",
            description="Password",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_password_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.kwargs["render_kw"]["kyc_type"] == "password"


class TestCustomPostcodeField:
    """Test custom_postcode_field function."""

    def test_returns_field_with_postcode_kyc_type(self) -> None:
        """Test custom_postcode_field sets kyc_type='postcode'."""
        field = SurveyField(
            id="test_id",
            name="test_postcode",
            description="Postal code",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_postcode_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.kwargs["render_kw"]["kyc_type"] == "postcode"


class TestCustomUrlField:
    """Test custom_url_field function."""

    def test_returns_field_with_url_kyc_type(self) -> None:
        """Test custom_url_field sets kyc_type='url'."""
        field = SurveyField(
            id="test_id",
            name="test_url",
            description="Website URL",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_url_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.kwargs["render_kw"]["kyc_type"] == "url"


class TestCustomTextareaField:
    """Test custom_textarea_field function."""

    def test_returns_textarea_field(self) -> None:
        """Test custom_textarea_field returns a TextAreaField."""
        field = SurveyField(
            id="test_id",
            name="test_textarea",
            description="Long text",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_textarea_field(field, "M")

        assert isinstance(result, UnboundField)
        assert result.field_class is TextAreaField

    def test_label_contains_textarea_size_tag(self) -> None:
        """Test textarea label contains size instructions."""
        field = SurveyField(
            id="test_id",
            name="test_textarea",
            description="Long text",
            public_maxi=False,
            upper_message="",
        )

        result = custom_textarea_field(field, "O")

        assert TAG_AREA_SIZE in result.kwargs["label"]


class TestCustomTextarea300Field:
    """Test custom_textarea300_field function."""

    def test_label_contains_textarea300_size_tag(self) -> None:
        """Test textarea300 label contains size instructions."""
        field = SurveyField(
            id="test_id",
            name="test_textarea300",
            description="Short text",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_textarea300_field(field, "M")

        assert isinstance(result, UnboundField)
        assert TAG_AREA300_SIZE in result.kwargs["label"]


def test_fake_ontology_ajax() -> None:
    """Test _fake_ontology_ajax function."""
    result = _fake_ontology_ajax("test_param")

    # Should return a list of tuples
    assert isinstance(result, list)
    # First item should be the "choose" option
    assert result[0][0] == ""
    assert "test_param" in result[0][1]
    # Should have 21 total items (1 empty + 20 numbered)
    assert len(result) == 21
    # Check a numbered item
    assert "'test_param' 1" in result[1][0]


class TestCustomListField:
    """Test custom_list_field function."""

    def test_returns_unbound_field(self) -> None:
        """Test custom_list_field returns an UnboundField."""
        field = SurveyField(
            id="test_id",
            name="test_list",
            description="Select from list",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_list_field(field, "M", param="multi_langues")

        assert isinstance(result, UnboundField)
        assert result.kwargs["id"] == "test_id"

    def test_readonly_passes_to_field_constructor(self) -> None:
        """Test readonly=True passes readonly=1 to field constructor."""
        field = SurveyField(
            id="test_id",
            name="test_list",
            description="Select from list",
            public_maxi=False,
            upper_message="",
        )

        result = custom_list_field(field, "M", param="multi_langues", readonly=True)

        # Readonly is passed to field constructor, not render_kw
        assert result.kwargs["readonly"] == 1


class TestCustomCountryField:
    """Test custom_country_field function."""

    def test_returns_unbound_field(self) -> None:
        """Test custom_country_field returns an UnboundField."""
        field = SurveyField(
            id="test_id",
            name="test_country",
            description="Country; Region",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_country_field(field, "M", param="country_pays")

        assert isinstance(result, UnboundField)

    def test_readonly_passes_to_field_constructor(self) -> None:
        """Test readonly=True passes readonly=1 to field constructor."""
        field = SurveyField(
            id="test_id",
            name="test_country",
            description="Country; Region",
            public_maxi=False,
            upper_message="",
        )

        result = custom_country_field(field, "M", param="country_pays", readonly=True)

        # Readonly is passed to field constructor, not render_kw
        assert result.kwargs["readonly"] == 1


class TestCustomListFreeField:
    """Test custom_list_free_field function."""

    def test_returns_unbound_field(self) -> None:
        """Test custom_list_free_field returns an UnboundField."""
        field = SurveyField(
            id="test_id",
            name="test_list_free",
            description="Select or add new",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_list_free_field(field, "M", param="multi_langues")

        assert isinstance(result, UnboundField)

    def test_readonly_passes_to_field_constructor(self) -> None:
        """Test readonly=True passes readonly=1 to field constructor."""
        field = SurveyField(
            id="test_id",
            name="test_list_free",
            description="Select or add new",
            public_maxi=False,
            upper_message="",
        )

        result = custom_list_free_field(
            field, "O", param="multi_langues", readonly=True
        )

        # Readonly is passed to field constructor, not render_kw
        assert result.kwargs["readonly"] == 1


class TestCustomAjaxField:
    """Test custom_ajax_field function."""

    def test_returns_unbound_field(self) -> None:
        """Test custom_ajax_field returns an UnboundField."""
        field = SurveyField(
            id="test_id",
            name="test_ajax",
            description="Ajax select",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_ajax_field(field, "M", param="test_param")

        assert isinstance(result, UnboundField)

    def test_readonly_not_implemented(self) -> None:
        """Test that readonly is NOT implemented for ajax field (uses standard SelectField)."""
        field = SurveyField(
            id="test_id",
            name="test_ajax",
            description="Ajax select",
            public_maxi=False,
            upper_message="",
        )

        result = custom_ajax_field(field, "M", param="test_param", readonly=True)

        # Readonly is not implemented for ajax field
        # It uses standard SelectField which doesn't have readonly parameter
        assert "readonly" not in result.kwargs
        assert "disabled" not in result.kwargs.get("render_kw", {})


class TestCustomMultiFreeField:
    """Test custom_multi_free_field function."""

    def test_returns_unbound_field(self) -> None:
        """Test custom_multi_free_field returns an UnboundField."""
        field = SurveyField(
            id="test_id",
            name="test_multi_free",
            description="Multiple select with free text",
            public_maxi=False,
            upper_message="Test message",
        )

        result = custom_multi_free_field(field, "M", param="multi_langues")

        assert isinstance(result, UnboundField)

    def test_label_contains_many_choices_tag(self) -> None:
        """Test label contains many choices tag (free element tag not added)."""
        field = SurveyField(
            id="test_id",
            name="test_multi_free",
            description="Multiple select",
            public_maxi=False,
            upper_message="",
        )

        result = custom_multi_free_field(field, "O", param="multi_langues")

        # Only many choices tag is added, not free element
        assert TAG_MANY_CHOICES in result.kwargs["label"]


class TestCustomMultiField:
    """Test custom_multi_field function."""

    def test_returns_unbound_field_for_simple_list(self) -> None:
        """Test custom_multi_field returns UnboundField for simple list."""
        field = SurveyField(
            id="test_id",
            name="test_multi",
            description="Multiple select",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_multi_field(field, "M", param="multi_langues")

        assert isinstance(result, UnboundField)

    def test_returns_unbound_field_for_dual_select(self) -> None:
        """Test custom_multi_field returns UnboundField for dual select."""
        field = SurveyField(
            id="test_id",
            name="test_multi",
            description="Multiple select",
            public_maxi=True,
            upper_message="Test message",
        )

        result = custom_multi_field(field, "M", param="multidual_secteurs_detail")

        assert isinstance(result, UnboundField)

    def test_label_contains_many_choices_tag(self) -> None:
        """Test label contains TAG_MANY_CHOICES."""
        field = SurveyField(
            id="test_id",
            name="test_multi",
            description="Multiple select",
            public_maxi=False,
            upper_message="",
        )

        result = custom_multi_field(field, "O", param="multi_langues")

        assert TAG_MANY_CHOICES in result.kwargs["label"]
