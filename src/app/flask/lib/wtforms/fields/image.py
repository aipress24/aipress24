# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import widgets
from wtforms.fields.simple import FileField

from .base import BaseWidget


class ImageWidget(widgets.Input, BaseWidget):
    def __call__(self, field: ImageField, **kwargs):
        template = self.get_template("image.j2")
        return template.render(field=field)


class ImageField(FileField):
    widget = ImageWidget()
