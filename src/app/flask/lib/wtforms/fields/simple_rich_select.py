# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import widgets
from wtforms.fields.choices import SelectField

from .base import BaseWidget


class SimpleRichSelectWidget(widgets.Select, BaseWidget):
    def __call__(self, field: SimpleRichSelectField, **kwargs):
        template = self.get_template("rich_select.j2")
        return template.render(field=field)


class SimpleRichSelectField(SelectField):
    widget = SimpleRichSelectWidget()

    def __init__(self, label=None, validators=None, **kwargs) -> None:
        super().__init__(label, validators, **kwargs)

    def get_choices_for_js(self):
        return [list(tup) for tup in self.choices]
