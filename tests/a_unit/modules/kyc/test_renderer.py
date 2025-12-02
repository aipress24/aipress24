# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/renderer.py"""

from __future__ import annotations

from markupsafe import Markup

from app.modules.kyc.renderer import (
    CSS_CLASS,
    CSS_CLASS_RO,
    DEFAULT_CSS,
    DEFAULT_CSS_RO,
    _field_type,
    _is_mandatory_field,
    _render_field,
    _upper_message,
    render_field,
)


class StubField:
    """Stub field for testing renderer functions."""

    def __init__(self, render_kw=None, errors=None):
        self.render_kw = render_kw
        self.errors = errors or []

    def __call__(self, **kwargs):
        """Return HTML for the field widget."""
        css_class = kwargs.get("class", "")
        return f'<input type="text" class="{css_class}" />'

    def label(self, **kwargs):
        """Return HTML for the field label."""
        css_class = kwargs.get("class", "")
        return f'<label class="{css_class}">Test Label</label>'


def test_upper_message_extracts_kyc_message() -> None:
    """Test _upper_message extracts and strips kyc_message from render_kw."""
    assert _upper_message(StubField({"kyc_message": "  Note  "})) == "Note"
    assert _upper_message(StubField({"kyc_message": ""})) == ""
    assert _upper_message(StubField({})) == ""
    assert _upper_message(StubField(None)) == ""


def test_field_type_extracts_kyc_type() -> None:
    """Test _field_type extracts kyc_type, defaulting to 'string'."""
    assert _field_type(StubField({"kyc_type": "email"})) == "email"
    assert _field_type(StubField({"kyc_type": "boolean"})) == "boolean"
    assert _field_type(StubField({})) == "string"
    assert _field_type(StubField(None)) == "string"


def test_is_mandatory_field_checks_kyc_code() -> None:
    """Test _is_mandatory_field returns True only for kyc_code='M'."""
    assert _is_mandatory_field(StubField({"kyc_code": "M"})) is True
    assert _is_mandatory_field(StubField({"kyc_code": "O"})) is False
    assert _is_mandatory_field(StubField({})) is False


def test_css_class_dictionaries_have_expected_keys() -> None:
    """Test CSS_CLASS and CSS_CLASS_RO have expected field types."""
    expected = ["boolean", "string", "photo", "email", "tel", "password", "code", "url"]
    for field_type in expected:
        assert field_type in CSS_CLASS and field_type in CSS_CLASS_RO

    assert DEFAULT_CSS and DEFAULT_CSS_RO
    assert "focus:" in DEFAULT_CSS and "focus:" in DEFAULT_CSS_RO


def test_render_field_returns_markup_for_string_field() -> None:
    """Test _render_field returns Markup for string field type."""
    field = StubField({"kyc_type": "string"})
    result = _render_field(field)

    assert isinstance(result, Markup)
    assert DEFAULT_CSS in str(result)


def test_render_field_uses_readonly_css_when_readonly() -> None:
    """Test _render_field uses readonly CSS classes when readonly=True."""
    field = StubField({"kyc_type": "string", "readonly": True})
    result = _render_field(field)

    assert isinstance(result, Markup)
    assert DEFAULT_CSS_RO in str(result)


def test_render_field_uses_boolean_css_for_boolean_type() -> None:
    """Test _render_field uses boolean CSS class for boolean field type."""
    field = StubField({"kyc_type": "boolean"})
    result = _render_field(field)

    assert isinstance(result, Markup)
    assert CSS_CLASS["boolean"] in str(result)


def test_render_field_uses_default_css_for_unknown_type() -> None:
    """Test _render_field falls back to DEFAULT_CSS for unknown field types."""
    field = StubField({"kyc_type": "unknown_type"})
    result = _render_field(field)

    assert isinstance(result, Markup)
    assert DEFAULT_CSS in str(result)


def test_render_field_uses_email_css_for_email_type() -> None:
    """Test _render_field uses email CSS class for email field type."""
    field = StubField({"kyc_type": "email"})
    result = _render_field(field)

    assert isinstance(result, Markup)
    assert CSS_CLASS["email"] in str(result)


def test_render_full_field_returns_markup() -> None:
    """Test render_field returns Markup with complete field structure."""
    field = StubField({"kyc_type": "string"})
    result = render_field(field)

    assert isinstance(result, Markup)
    # Should contain label
    assert "Test Label" in str(result)
    # Should contain the input
    assert "<input" in str(result)


def test_render_full_field_with_errors() -> None:
    """Test render_field includes error messages."""
    field = StubField({"kyc_type": "string"}, errors=["This field is required"])
    result = render_field(field)

    assert isinstance(result, Markup)
    assert "This field is required" in str(result)
    assert "text-red-600" in str(result)


def test_render_full_field_with_upper_message() -> None:
    """Test render_field includes upper message when kyc_message is set."""
    field = StubField({"kyc_type": "string", "kyc_message": "Important note"})
    result = render_field(field)

    assert isinstance(result, Markup)
    assert "Important note" in str(result)


def test_render_full_field_boolean_puts_widget_before_label() -> None:
    """Test render_field places checkbox before label for boolean fields."""
    field = StubField({"kyc_type": "boolean"})
    result = render_field(field)

    assert isinstance(result, Markup)
    result_str = str(result)
    # For boolean, input comes before label
    input_pos = result_str.find("<input")
    label_pos = result_str.find("Test Label")
    assert input_pos < label_pos


def test_render_full_field_non_boolean_puts_label_before_widget() -> None:
    """Test render_field places label before input for non-boolean fields."""
    field = StubField({"kyc_type": "string"})
    result = render_field(field)

    assert isinstance(result, Markup)
    result_str = str(result)
    # For non-boolean, label comes before input
    input_pos = result_str.find("<input")
    label_pos = result_str.find("Test Label")
    assert label_pos < input_pos


def test_render_full_field_with_multiple_errors() -> None:
    """Test render_field displays multiple error messages."""
    field = StubField(
        {"kyc_type": "string"},
        errors=["Error 1", "Error 2", "Error 3"],
    )
    result = render_field(field)

    assert isinstance(result, Markup)
    result_str = str(result)
    assert "Error 1" in result_str
    assert "Error 2" in result_str
    assert "Error 3" in result_str
