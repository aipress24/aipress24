# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from markupsafe import Markup
from wtforms import widgets
from wtforms.fields.choices import SelectMultipleField

from .base import BaseWidget


class SimpleRichSelectMultipleWidget(widgets.Select, BaseWidget):
    def __call__(self, field: SimpleRichSelectMultipleField, **kwargs):
        template = self.get_template("rich_select_multiple.j2")
        # #0162: return Markup, not bare str (autoescape class).
        return Markup(template.render(field=field))


class SimpleRichSelectMultipleField(SelectMultipleField):
    widget = SimpleRichSelectMultipleWidget()
    multiple = True

    def __init__(self, label=None, validators=None, **kwargs) -> None:
        super().__init__(label, validators, **kwargs)

    def get_choices_for_js(self) -> list[dict[str, Any]]:
        """TomSelect options: a list of `{value, label}` dicts.

        Built from `iter_choices`, which is what the widget itself
        renders from. Unpacking `self.choices` directly only handles the
        `(value, label)` form; WTForms also accepts bare strings and
        `(value, label, render_kw)` triples, and a dict for optgroups.
        """
        return [
            {"value": str(value), "label": str(label)}
            for value, label, *_ in self.iter_choices()
        ]
