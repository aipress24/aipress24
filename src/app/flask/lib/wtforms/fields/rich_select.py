# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from markupsafe import Markup
from wtforms import widgets
from wtforms.fields.choices import SelectField

from app.flask.forms import get_choices

from .base import BaseWidget


class RichSelectWidget(widgets.Select, BaseWidget):
    def __call__(self, field: RichSelectField, **kwargs):
        template = self.get_template("rich_select.j2")
        # #0162: return Markup, not bare str (autoescape class).
        return Markup(template.render(field=field))


class RichSelectField(SelectField):
    widget = RichSelectWidget()

    key: str

    def __init__(self, label=None, validators=None, key=None, **kwargs) -> None:
        if key is not None:
            self.key = key
        super().__init__(label, validators, choices=self._choices, **kwargs)

    def _choices(self):
        """(value, label) pairs. A vocabulary is either a list of labels,
        stored as they read, or a mapping of stored codes to labels."""
        values = get_choices(self.key)
        if isinstance(values, dict):
            return list(values.items())
        # pyrefly: ignore [not-iterable]
        return [(value, value) for value in values]

    def get_choices_for_js(self):
        # Ensure string values so JavaScript cannot corrupt large integers.
        return [[str(value), str(label)] for value, label in self._choices()]
