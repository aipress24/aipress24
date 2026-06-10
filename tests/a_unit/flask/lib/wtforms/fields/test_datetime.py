# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.datetime`.

`DateTimeField` overrides WTForms' default to accept three formats —
the HTML5 `datetime-local` shape (with and without seconds) plus the
classic space-separated one. The widget swaps `input_type` to
`datetime-local` so browsers show the HTML5 picker.
"""

from __future__ import annotations

from datetime import datetime

from werkzeug.datastructures import MultiDict
from wtforms import Form

from app.flask.lib.wtforms.fields.datetime import DateTimeField, DateTimeInput


class _DTForm(Form):
    when = DateTimeField()


class _DTFormCustom(Form):
    when = DateTimeField(format="%d/%m/%Y %H:%M")


class TestDateTimeFieldDefaultFormats:
    def test_parses_space_separated_with_seconds(self) -> None:
        form = _DTForm(formdata=MultiDict({"when": "2026-06-10 14:30:00"}))
        assert form.validate()
        # wtforms DateTimeField returns naive datetime — match it.
        assert form.when.data == datetime(2026, 6, 10, 14, 30, 0)  # noqa: DTZ001

    def test_parses_html5_iso_with_seconds(self) -> None:
        form = _DTForm(formdata=MultiDict({"when": "2026-06-10T14:30:00"}))
        assert form.validate()
        assert form.when.data == datetime(2026, 6, 10, 14, 30, 0)  # noqa: DTZ001

    def test_parses_html5_iso_without_seconds(self) -> None:
        form = _DTForm(formdata=MultiDict({"when": "2026-06-10T14:30"}))
        assert form.validate()
        assert form.when.data == datetime(2026, 6, 10, 14, 30)  # noqa: DTZ001

    def test_rejects_unsupported_format(self) -> None:
        form = _DTForm(formdata=MultiDict({"when": "10/06/2026 14:30"}))
        assert not form.validate()
        assert form.when.data is None


class TestDateTimeFieldCustomFormat:
    def test_explicit_format_overrides_defaults(self) -> None:
        form = _DTFormCustom(formdata=MultiDict({"when": "10/06/2026 14:30"}))
        assert form.validate()
        assert form.when.data == datetime(2026, 6, 10, 14, 30)  # noqa: DTZ001

    def test_explicit_format_excludes_default_iso(self) -> None:
        form = _DTFormCustom(formdata=MultiDict({"when": "2026-06-10T14:30:00"}))
        assert not form.validate()


class TestDateTimeInputWidget:
    def test_input_type_is_datetime_local(self) -> None:
        """The HTML5 `datetime-local` picker is the whole point — pin it."""
        assert DateTimeInput.input_type == "datetime-local"

    def test_widget_is_used_by_default(self) -> None:
        field = _DTForm().when
        assert isinstance(field.widget, DateTimeInput)
