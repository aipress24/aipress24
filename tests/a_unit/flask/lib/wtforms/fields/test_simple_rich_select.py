# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.simple_rich_select`.

Mirror image of `rich_select`, minus the vocabulary lookup: choices
are passed explicitly. The `get_choices_for_js` helper still
stringifies values (so JS doesn't truncate Snowflake-ish ids), and
keeps the human-readable label intact.
"""

from __future__ import annotations

from wtforms import Form

from app.flask.lib.wtforms.fields.simple_rich_select import (
    SimpleRichSelectField,
    SimpleRichSelectWidget,
)


class TestSimpleRichSelectFieldChoices:
    def test_choices_round_trip(self) -> None:
        class _F(Form):
            sector = SimpleRichSelectField(
                choices=[("politics", "Politics"), ("tech", "Tech")]
            )

        assert _F().sector.choices == [
            ("politics", "Politics"),
            ("tech", "Tech"),
        ]


class TestSimpleRichSelectGetChoicesForJs:
    def test_stringifies_int_values_preserves_labels(self) -> None:
        big = 2**60

        class _F(Form):
            media = SimpleRichSelectField(
                choices=[(big, "Le Monde"), (1, "Libé"), (2, "Le Figaro")]
            )

        assert _F().media.get_choices_for_js() == [
            [str(big), "Le Monde"],
            ["1", "Libé"],
            ["2", "Le Figaro"],
        ]

    def test_string_values_round_trip(self) -> None:
        class _F(Form):
            opt = SimpleRichSelectField(choices=[("yes", "Yes"), ("no", "No")])

        assert _F().opt.get_choices_for_js() == [
            ["yes", "Yes"],
            ["no", "No"],
        ]

    def test_none_choices_yield_empty_list(self) -> None:
        """`self.choices or []` is the guard against a freshly-built
        field whose choices are still `None`."""

        class _F(Form):
            opt = SimpleRichSelectField(choices=[])

        # Force the None path post-construction.
        field = _F().opt
        field.choices = None
        assert field.get_choices_for_js() == []

    def test_empty_choices_yield_empty_list(self) -> None:
        class _F(Form):
            opt = SimpleRichSelectField(choices=[])

        assert _F().opt.get_choices_for_js() == []


class TestSimpleRichSelectWidget:
    def test_widget_is_used_by_default(self) -> None:
        class _F(Form):
            opt = SimpleRichSelectField(choices=[])

        assert isinstance(_F().opt.widget, SimpleRichSelectWidget)
