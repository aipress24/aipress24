# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import current_app
from wtforms import widgets
from wtforms.fields.choices import SelectField


def convert_country_to_tom_choices_js(choices: list) -> list:
    return [
        {
            "value": country[0],
            "label": country[1],
        }
        for country in choices
    ]


class CountrySelectWidget(widgets.Select):
    def __call__(self, field: CountrySelectField, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "country_select.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class CountrySelectField(SelectField):
    widget = CountrySelectWidget()
    double_select = True

    def __init__(
        self,
        **kwargs,
    ):
        self.id2 = kwargs.pop("id2", "")
        self.name2 = kwargs.pop("name2", "")
        self.label2 = kwargs.pop("label2", "")
        self.lock = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = False
        self.create = False
        self.data2 = kwargs.pop("data2", "")
        # self.choices = kwargs.pop("choices", [])

    def get_tom_choices_for_js(self) -> list:
        """Data structure for country:

        [('AFG', 'Afghanistan'),
         ('ZAF', 'Afrique du Sud'),
         ...
        """
        return convert_country_to_tom_choices_js(self.choices)

    def get_data(self) -> str:
        if self.data is None:
            return repr("")
        return repr(self.data)

    def get_data2(self) -> str:
        if self.data2 is None:
            return repr([])
        return repr(self.data2)
