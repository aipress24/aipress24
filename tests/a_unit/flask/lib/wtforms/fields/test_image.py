# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.wtforms.fields.image.ImageField`.

Thin subclass of WTForms' `FileField`. The class itself is mostly
declarative — pin the widget + base-class so a refactor doesn't
silently drop the image template.
"""

from __future__ import annotations

from wtforms import Form
from wtforms.fields.simple import FileField

from app.flask.lib.wtforms.fields.image import ImageField, ImageWidget


class _F(Form):
    photo = ImageField()


class TestImageField:
    def test_is_a_file_field(self) -> None:
        assert isinstance(_F().photo, FileField)

    def test_uses_image_widget(self) -> None:
        assert isinstance(_F().photo.widget, ImageWidget)
