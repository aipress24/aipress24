# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from advanced_alchemy.types import FileObject
from flask import current_app
from wtforms import FileField, widgets


class ValidImageWidget(widgets.Input):
    def __call__(self, field: ValidImageField, **kwargs):
        template = self.get_template()
        return template.render(field=field, **kwargs)

    def get_template(self):
        template_path = Path(__file__).parent / "valid_image.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class ValidImageField(FileField):
    widget = ValidImageWidget()

    def __init__(
        self,
        *,
        file_object: FileObject | None = None,
        **kwargs,
    ) -> None:
        self.max_image_size = kwargs.pop("max_image_size", 2048)  # KB
        self.is_required = kwargs.pop("is_required", False)
        self.readonly = kwargs.pop("readonly", False)
        self.file_object = kwargs.pop("file_object", None)
        super().__init__(**kwargs)
        self.multiple = False

    @property
    def preload_filename(self) -> str:
        if self.file_object:
            return self.file_object.filename or ""
        return ""

    @property
    def preload_filesize(self) -> int:
        if self.file_object and self.file_object.size:
            return self.file_object.size
        return 0

    def get_image_url(self) -> str | None:
        if self.file_object:
            return self.file_object.sign()
        return None

    def id_preload_name(self) -> str:
        return self.id + "_preload_name"

    def name_preload_name(self) -> str:
        return self.name + "_preload_name"
