# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import current_app
from wtforms import widgets
from wtforms.fields.choices import SelectMultipleField


def convert_dual_choices_js(choices: dict) -> dict:
    """Data structure:

    # Argument 'choices':
    #     {'Associations': ['Actions humanitaires', 'Communication et sensibilisatio ...
    #
    {
        "field1": [ ('Associations','Associations'), ...]
        "field2": [ ( 'Associations /Actions humanitaires',
                      'Associations / Actions humanitaires'), ...
    }

    Output:
    {
        "field1": [ {"value": 'Associations', "label": 'Associations'} ...
        "field2": [ {"value": 'Associations / Actions humanitaires',  "label":
            'Associations / Actions humanitaires'}, ...
    }
    """
    field1 = [
        {
            "value": val[0],
            "label": val[1],
        }
        for val in choices["field1"]
    ]
    field2 = []
    for values in choices["field2"].values():
        for val in values:
            field2.append({
                "value": val[0],
                "label": val[1],
            })
    result = {"field1": field1, "field2": field2}
    return result


class DualSelectWidget(widgets.Select):
    def __call__(self, field: DualSelectField, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "dual_select_multi.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class DualSelectField(SelectMultipleField):
    widget = DualSelectWidget()
    double_select = True

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.id2 = kwargs.pop("id2", "")
        self.name2 = kwargs.pop("name2", "")
        self.label2 = kwargs.pop("label2", "")
        self.lock = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = True
        self.create = False
        self.data2 = kwargs.pop("data2", "")

    def get_dual_tom_choices_for_js(self) -> dict:
        """Data structure:

        # Input:
        #     {'Associations': ['Actions humanitaires',
        #         'Communication et sensibilisatio ...

        Output:
        {
            "field1": [ {"value": 'Associations', "label": 'Associations'} ...
            "field2": [ {"value": 'Associations / Actions humanitaires',  "label":
                'Associations / Actions humanitaires'} ...
        }
        """
        return convert_dual_choices_js(self.choices)

    def get_data(self) -> list:
        if self.data is None:
            return repr([])
        return repr(self.data)

    def get_data2(self) -> list:
        if self.data2 is None:
            return repr([])
        return repr(self.data2)
