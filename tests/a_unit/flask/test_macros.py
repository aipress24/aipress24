# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Cover the `@macro` decorator that wraps the return value in
`markupsafe.Markup`.

This is a small wrapper but it's load-bearing: every macro in
`app.ui.macros` (tab bars, icons, tables, images) returns plain
`str` HTML built with `webbits.html.h`. When the project enabled
autoescape on `.j2` templates, those plain strings started being
escaped on render — tab bars rendered as visible angle brackets.

The decorator guarantees `Markup` on the way out, so the macros
remain renderable under autoescape without per-call-site `|safe`.
"""

from __future__ import annotations

from markupsafe import Markup

from app.flask.lib.macros import macro


class TestMacroDecorator:
    def test_str_return_is_wrapped_in_markup(self):
        @macro
        def foo():
            return "<div>hi</div>"

        result = foo()
        assert isinstance(result, Markup)
        assert str(result) == "<div>hi</div>"

    def test_markup_return_passes_through_unchanged(self):
        original = Markup("<p>already-safe</p>")

        @macro
        def foo():
            return original

        result = foo()
        assert result is original

    def test_none_return_is_empty_markup(self):
        @macro
        def foo():
            return None

        result = foo()
        assert isinstance(result, Markup)
        assert str(result) == ""

    def test_args_are_passed_through(self):
        @macro
        def foo(label, *, suffix="!"):
            return f"<b>{label}{suffix}</b>"

        result = foo("hello", suffix="?")
        assert str(result) == "<b>hello?</b>"

    def test_wrapped_function_keeps_its_name(self):
        @macro
        def m_my_widget():
            return "<x/>"

        # The wrapper exposes the same __name__ so
        # `register_macros` registers it under the expected key.
        assert m_my_widget.__name__ == "m_my_widget"
