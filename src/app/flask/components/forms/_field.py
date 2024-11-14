# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from attr import frozen
from markupsafe import Markup

from app.flask.lib.templates import get_related_template
from app.lib.names import to_kebab_case

from ._constants import get_choices


@frozen
class Field:
    spec: dict
    value: Any

    @classmethod
    def type(cls):
        return to_kebab_case(cls.__name__[0:-5])

    def render_edit(self, **ctx) -> str:
        path = f"templates/fields/{self.type()}.j2"
        template = get_related_template(self, path)
        return Markup(template.render(field=self))

    def render_view(self, **ctx) -> str:
        return Markup(self.value)

    def __getitem__(self, item):
        if item in self.extras():
            return self.extras()[item]
        return self.spec[item]

    def __getattr__(self, item):
        if item == "__deepcopy__":
            raise AttributeError
        if item in self.extras():
            return self.extras()[item]
        return self.spec[item]

    def extras(self):
        return {}


#
# Date & Time
#
@frozen
class DateField(Field):
    pass


@frozen
class TimeField(Field):
    pass


@frozen
class DateTimeField(Field):
    pass


@frozen
class DatetimeField(Field):
    pass


#
# Others
#
@frozen
class ImageField(Field):
    pass


@frozen
class InputField(Field):
    pass


@frozen
class RichTextField(Field):
    pass


@frozen
class SelectField(Field):
    def extras(self):
        key = self.spec["key"]
        choices = get_choices()
        if key in choices:
            options = self.get_options(key)
        else:
            options = {}

        return {
            "options": options,
        }

    def get_options(self, key):
        choices = get_choices()
        return [{"value": item, "label": item, "selected": ""} for item in choices[key]]


@frozen
class RichSelectField(Field):
    def extras(self):
        key = self.spec["key"]
        choices = get_choices()
        if key in choices:
            options = self.get_options(key)
        else:
            options = {}

        return {
            "options": options,
            "value": "",
        }

    def get_options(self, key):
        choices = get_choices()
        return [{"value": item, "label": item, "selected": ""} for item in choices[key]]


@frozen
class TextField(Field):
    pass


@frozen
class VideoField(Field):
    pass
