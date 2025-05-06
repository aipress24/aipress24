# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from pathlib import Path

from flask import current_app
from wtforms import widgets
from wtforms.fields.choices import SelectMultipleField


def convert_to_tom_choices_js(choices: list | dict) -> list:
    if isinstance(choices, list):
        # required by choices.js : list of dict
        return [{"value": item[0], "label": item[1]} for item in choices]
    if isinstance(choices, dict):
        # dict is a dict of groups of labels:
        return _dict_to_group_tom_choices(choices)
    print(f"{type(choices)}", file=sys.stderr)
    print(f"{choices=}", file=sys.stderr)
    raise TypeError


def _dict_to_group_tom_choices(choices: dict) -> list:
    # Fixme:  this fromat seems ok for choices.setChoices()
    # but neither at init time of for wtforms???
    groups = []
    for group, items in choices.items():
        choices_group = [
            {"optgroup": group, "value": label, "label": label} for label in items
        ]
        groups.extend(choices_group)

    # fails on the production server (OSError: [Errno 90] Message too long)
    # debug(groups)
    return groups


class SelectMultiSimpleWidget(widgets.Select):
    def __call__(self, field: SelectMultiSimpleField, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "select_multi_simple.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class SelectMultiSimpleField(SelectMultipleField):
    widget = SelectMultiSimpleWidget()

    def __init__(
        self,
        **kwargs,
    ):
        self.lock = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = True
        self.create = False
        self.choices = kwargs["choices"]

    def get_tom_choices_for_js(self) -> list:
        return convert_to_tom_choices_js(self.choices)

    def get_data(self) -> list:
        if self.data is None:
            return []
        return self.data
