# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import io
from collections import OrderedDict
from typing import Any, cast

import tomli
from flask import current_app
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from markupsafe import Markup

from app.flask.lib.templates import get_related_template

from ._field import Field

# Used to please Tailwind
IGNORE = """
sm:col-span-1
sm:col-span-2
sm:col-span-3
sm:col-span-4
sm:col-span-5
sm:col-span-6
"""


def get_form_specs(name_or_file: str | io.TextIOBase) -> dict:
    match name_or_file:
        case str(name):
            config = current_app.config
            forms_dir = config["FORMS_DIR"]
            env = Environment(loader=FileSystemLoader(forms_dir), autoescape=True)
            toml = env.get_template(name).render()
        case io.TextIOBase():
            toml = name_or_file.read()
        case _:
            raise ValueError

    return tomli.loads(toml)


class Form:
    form_specs: dict
    model: Any
    fields: OrderedDict
    _action_url: str = ""

    def __init__(self, specs: dict, model=None):
        self.form_specs = specs
        self.model = model
        self.fields = self._get_fields()

    @staticmethod
    def from_file(name_or_file: str | io.TextIOBase) -> Form:
        specs = get_form_specs(name_or_file)
        return Form(specs)

    def render(self) -> Markup:
        groups = self._get_groups()

        template = get_related_template(self, "templates/form.j2")
        ctx = {
            "groups": groups,
            "form": self,
            "model": self.model,
            "render_field": self.render_field,
        }
        return Markup(template.render(**ctx).strip())

    def render_field(self, field: Field) -> str:
        return field.render()

    def _get_fields(self) -> OrderedDict:
        _fields = OrderedDict()
        for field_id, field_specs in self.form_specs["field"].items():
            if "type" not in field_specs:
                field_specs["type"] = "text"
            if "width" not in field_specs:
                field_specs["width"] = 6

            field_specs["id"] = field_id
            _fields[field_id] = self._get_field(field_specs)
        return _fields

    def _get_field(self, field_spec: dict) -> Field:
        field_id = field_spec["id"]
        field_classes = Field.__subclasses__()
        for field_cls in field_classes:
            if field_cls.type() == field_spec["type"]:
                break
        else:
            field_type = field_spec["type"]
            raise ValueError(f"Unknown field type: {field_type} for field: {field_id}")

        field_cls = cast(type[Field], field_cls)

        if self.model:
            if not hasattr(self.model, field_id):
                logger.warning("Model {} does not have field {}", self.model, field_id)
            field_value = getattr(self.model, field_id, "FIXME")
        else:
            field_value = ""
        return field_cls(field_spec, field_value)

    def _get_groups(self):
        groups = []
        for group_id, group in self.form_specs["group"].items():
            group["id"] = group_id
            group["fields"] = [
                field for field in self.fields.values() if field["group"] == group_id
            ]
            groups.append(group)
        return groups
