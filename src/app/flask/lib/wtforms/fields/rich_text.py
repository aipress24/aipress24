# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import ClassVar

from wtforms.fields.simple import StringField

from .base import BaseWidget


class RichTextWidget(BaseWidget):
    """
    Renders a multi-line text area.

    `rows` and `cols` ought to be passed as keyword args when rendering.
    """

    validation_attrs: ClassVar = [
        "required",
        "disabled",
        "readonly",
        "maxlength",
        "minlength",
    ]

    # def __call__(self, field, **kwargs):
    #     kwargs.setdefault("id", field.id)
    #     flags = getattr(field, "flags", {})
    #     for k in dir(flags):
    #         if k in self.validation_attrs and k not in kwargs:
    #             kwargs[k] = getattr(flags, k)
    #
    #     return Markup(
    #         "<textarea %s>\r\n%s</textarea>"
    #         % (html_params(name=field.name, **kwargs), escape(field._value()))
    #     )

    def __call__(self, field: RichTextField, **kwargs):
        template = self.get_template("rich_text.j2")
        ctx = {
            "field": field,
        }
        return template.render(**ctx)


class RichTextField(StringField):
    widget = RichTextWidget()

    def get_value(self):
        return self._value()
