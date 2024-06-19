# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import current_app
from wtforms.fields.simple import StringField


class RichTextWidget:
    """
    Renders a multi-line text area.

    `rows` and `cols` ought to be passed as keyword args when rendering.
    """

    validation_attrs = ["required", "disabled", "readonly", "maxlength", "minlength"]

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
        template = self.get_template()
        ctx = {
            "field": field,
        }
        return template.render(**ctx)

    def get_template(self):
        template_path = Path(__file__).parent / "rich_text.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class RichTextField(StringField):
    widget = RichTextWidget()

    def get_value(self):
        return self._value()
