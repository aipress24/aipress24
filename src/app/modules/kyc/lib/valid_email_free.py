# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import current_app
from wtforms import StringField, widgets


class ValidEmailFreeWidget(widgets.EmailInput):
    def __call__(self, field: ValidEmailFree, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "valid_email_free.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class ValidEmailFree(StringField):
    widget = ValidEmailFreeWidget()

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.readonly = kwargs.pop("readonly", False)
        super().__init__(**kwargs)

    def get_data(self) -> str:
        if self.data is None:
            return ""
        return self.data
