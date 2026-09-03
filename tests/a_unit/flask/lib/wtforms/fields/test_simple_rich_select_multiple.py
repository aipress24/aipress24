# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""`SimpleRichSelectMultipleField.get_choices_for_js`.

The field feeds TomSelect a list of `{value, label}` dicts. It subclasses
`SelectMultipleField`, so it inherits that field's contract for
`choices`: a bare string, a `(value, label)` pair, a
`(value, label, render_kw)` triple, or a dict of option groups. Reading
`self.choices` directly only ever handled the pair, and anything else
raised on unpacking — so these pin every shape the base class accepts.
"""

from __future__ import annotations

import pytest
from wtforms import Form

from app.flask.lib.wtforms.fields.simple_rich_select_multiple import (
    SimpleRichSelectMultipleField,
)


def _options(choices) -> list[dict[str, str]]:
    class TestForm(Form):
        field = SimpleRichSelectMultipleField("Label", choices=choices)

    return TestForm().field.get_choices_for_js()


def test_pairs_are_the_common_case() -> None:
    assert _options([("a", "Alpha"), ("b", "Beta")]) == [
        {"value": "a", "label": "Alpha"},
        {"value": "b", "label": "Beta"},
    ]


def test_a_bare_string_is_its_own_label() -> None:
    """WTForms renders `choices=["x"]` as value and label alike."""
    assert _options(["x", "y"]) == [
        {"value": "x", "label": "x"},
        {"value": "y", "label": "y"},
    ]


def test_a_triple_keeps_value_and_label_and_drops_render_kw() -> None:
    """The third member is per-option `render_kw`, which TomSelect ignores."""
    assert _options([("c", "Gamma", {"disabled": True})]) == [
        {"value": "c", "label": "Gamma"}
    ]


def test_option_groups_are_flattened() -> None:
    """A dict declares optgroups; TomSelect wants the options themselves."""
    assert _options({"G1": [("d", "Delta")], "G2": [("e", "Epsilon")]}) == [
        {"value": "d", "label": "Delta"},
        {"value": "e", "label": "Epsilon"},
    ]


@pytest.mark.parametrize("choices", [[], None])
def test_nothing_to_offer_is_an_empty_list(choices) -> None:
    assert _options(choices) == []


def test_values_and_labels_are_strings() -> None:
    """TomSelect is given JSON: ints would come back as strings anyway."""
    assert _options([(1, 2)]) == [{"value": "1", "label": "2"}]
