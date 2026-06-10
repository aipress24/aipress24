# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.rich_select.RichSelectField`.

The field resolves its choices lazily via `app.flask.forms.get_choices(key)`.
We exercise the real "language" and "copyright-mention" keys (pure
constants in `app.settings.vocabularies`, no SVCS / DB) for the
straight cases, then patch in an integer vocabulary for the
big-int defense — the whole reason `get_choices_for_js` stringifies
values is so JavaScript cannot round ids > 2**53 (#0231).
"""

from __future__ import annotations

import pytest
from wtforms import Form

from app.flask.lib.wtforms.fields.rich_select import (
    RichSelectField,
    RichSelectWidget,
)


class _LanguageForm(Form):
    lang = RichSelectField(key="language")


class _CopyrightForm(Form):
    mention = RichSelectField(key="copyright-mention")


class TestRichSelectFieldChoices:
    def test_choices_come_from_get_choices(self) -> None:
        form = _LanguageForm()
        # `language` resolves to `voc.LANGUAGES` — a non-empty list of
        # human-readable language names.
        assert form.lang.choices
        # `_choices` is shaped (value, value) so the JS renderer can
        # mirror it without extra plumbing.
        assert all(v == label for v, label in form.lang.choices)
        assert ("Français", "Français") in form.lang.choices

    def test_key_stored_on_field(self) -> None:
        assert _LanguageForm().lang.key == "language"

    def test_distinct_keys_give_distinct_vocabularies(self) -> None:
        langs = {v for v, _ in _LanguageForm().lang.choices}
        mentions = {v for v, _ in _CopyrightForm().mention.choices}
        # The two vocabularies have nothing in common — sanity-check
        # that the `key` lookup actually routes per field.
        assert langs.isdisjoint(mentions)


class TestRichSelectGetChoicesForJs:
    def test_stringifies_values(self) -> None:
        js_choices = _LanguageForm().lang.get_choices_for_js()
        # Every entry is a [str, str] pair, even if the source list
        # held non-strings.
        assert all(
            isinstance(v, str) and isinstance(label, str) for v, label in js_choices
        )
        assert ["Français", "Français"] in js_choices

    def test_stringifies_big_int_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The whole point of `get_choices_for_js` (per the source
        comment) is to defend against JS losing precision on ids
        above 2**53. Real vocabularies are string-only, so we have
        to inject a synthetic int vocabulary to exercise the
        defense."""
        big = 2**60

        monkeypatch.setattr(
            "app.flask.lib.wtforms.fields.rich_select.get_choices",
            lambda key: [big, 1, 2] if key == "_ids" else [],
        )

        class _F(Form):
            ids = RichSelectField(key="_ids")

        assert _F().ids.get_choices_for_js() == [
            [str(big), str(big)],
            ["1", "1"],
            ["2", "2"],
        ]


class TestRichSelectWidget:
    def test_widget_is_used_by_default(self) -> None:
        assert isinstance(_LanguageForm().lang.widget, RichSelectWidget)
