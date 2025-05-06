# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import widgets
from wtforms.fields.choices import SelectField

from app.flask.forms import get_choices

from .base import BaseWidget


class RichSelectWidget(widgets.Select, BaseWidget):
    def __call__(self, field: RichSelectField, **kwargs):
        template = self.get_template("rich_select.j2")
        return template.render(field=field)


class RichSelectField(SelectField):
    widget = RichSelectWidget()

    key: str

    def __init__(self, label=None, validators=None, key=None, **kwargs) -> None:
        if key is not None:
            self.key = key
        super().__init__(label, validators, choices=self._choices, **kwargs)

    def _choices(self):
        values = get_choices(self.key)
        return [(value, value) for value in values]

    def get_choices_for_js(self):
        values = get_choices(self.key)
        return [[value, value] for value in values]
