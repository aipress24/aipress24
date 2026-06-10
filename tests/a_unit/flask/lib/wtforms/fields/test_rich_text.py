# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.rich_text.RichTextField`.

A `StringField` subclass with a custom widget. The interesting bit
is `get_value`, which exposes the protected `_value()` so the renderer
can read the field value without poking at protected attrs.
"""

from __future__ import annotations

from werkzeug.datastructures import MultiDict
from wtforms import Form

from app.flask.lib.wtforms.fields.rich_text import (
    RichTextField,
    RichTextWidget,
)


class _F(Form):
    body = RichTextField()


class TestRichTextFieldValue:
    def test_get_value_returns_string_value(self) -> None:
        form = _F(formdata=MultiDict({"body": "<p>Hello</p>"}))
        assert form.body.get_value() == "<p>Hello</p>"

    def test_get_value_on_empty_field_returns_empty_string(self) -> None:
        # WTForms' `_value()` returns "" for an unfilled StringField.
        assert _F().body.get_value() == ""

    def test_get_value_matches_internal_value(self) -> None:
        """Pin the contract : `get_value` is exactly `_value()`."""
        form = _F(formdata=MultiDict({"body": "some text"}))
        # Direct access to the protected helper, only to anchor the
        # equivalence — production code goes through `get_value`.
        assert form.body.get_value() == form.body._value()


class TestRichTextWidget:
    def test_widget_is_used_by_default(self) -> None:
        assert isinstance(_F().body.widget, RichTextWidget)
