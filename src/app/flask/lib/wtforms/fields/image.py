# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import current_app
from wtforms import widgets
from wtforms.fields.simple import FileField


class ImageWidget(widgets.Input):
    def __call__(self, field: ImageField, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "image.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class ImageField(FileField):
    widget = ImageWidget()
