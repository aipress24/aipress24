# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import base64
from pathlib import Path

from flask import current_app
from wtforms import FileField, widgets


class ValidBWImageWidget(widgets.Input):
    def __call__(self, field: ValidBWImageField, **kwargs):
        template = self.get_template()
        return template.render(field=field)

    def get_template(self):
        template_path = Path(__file__).parent / "valid_bw_image.j2"
        return current_app.jinja_env.from_string(template_path.read_text())


class ValidBWImageField(FileField):
    widget = ValidBWImageWidget()

    def __init__(
        self,
        **kwargs,
    ) -> None:
        self.max_image_size = kwargs.pop("max_image_size", 2048)  # KB
        self.data_b64 = kwargs.pop("data_b64", b"")
        self.preload_filename = kwargs.pop("filename", "")
        self.preload_filesize = kwargs.pop("filesize", 0)
        self.is_required = kwargs.pop("is_required", False)
        self.readonly = kwargs.pop("readonly", False)
        super().__init__(**kwargs)
        self.multiple = False

    def load_data(self, data: bytes) -> None:
        self.data = data or b""
        self.data_b64 = base64.standard_b64encode(self.data)
        self.preload_filename = "unused"
        self.preload_filesize = len(self.data)

    def preloaded_image(self) -> str:
        return self.data_b64.decode()

    def id_preload_name(self) -> str:
        return self.id + "_preload_name"

    def name_preload_name(self) -> str:
        return self.name + "_preload_name"

    def id_preload_b64(self) -> str:
        return self.id + "_preload_b64"

    def name_preload_b64(self) -> str:
        return self.name + "_preload_b64"
