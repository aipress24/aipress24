# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/renderer.py"""

from __future__ import annotations

from app.modules.kyc.renderer import (
    CSS_CLASS,
    CSS_CLASS_RO,
    DEFAULT_CSS,
    DEFAULT_CSS_RO,
    _field_type,
    _is_mandatory_field,
    _upper_message,
)


class StubField:
    """Stub field for testing renderer functions."""

    def __init__(self, render_kw=None):
        self.render_kw = render_kw


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
