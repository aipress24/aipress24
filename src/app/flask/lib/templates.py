# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
from copy import deepcopy
from pathlib import Path
from typing import Any

from flask import Response, current_app, render_template, render_template_string
from jinja2 import Template

from app.flask.lib.view_model import unwrap
from app.services.json_ld import to_json_ld
from app.services.opengraph import to_opengraph


def get_related_template(obj: Any, path: str) -> Template:
    try:
        file = Path(inspect.getfile(obj))
    except TypeError:
        file = Path(inspect.getfile(obj.__class__))
    if path:
        base_dir = file.parent
        template_file = base_dir / path
    else:
        template_file = file.with_suffix(".j2")

    template_str = template_file.read_text()
    template = current_app.jinja_env.from_string(template_str)
    return template


def templated(template_str):
    def decorator(f):
        def wrapper(*args, **kwargs) -> Response:
            result = f(*args, **kwargs)
            if isinstance(result, Response):
                return result
            ctx = result
            return TemplateResponse(ctx, template_str)

        return wrapper

    return decorator


class TemplateResponse(Response):
    def __init__(
        self,
        context: dict[str, Any] | None,
        template: str | Path,
        status=None,
        headers=None,
    ) -> None:
        self.template = template
        self.context = self.enrich_context(context)

        super().__init__(
            response=self.render(),
            status=status,
            headers=headers or {},
        )

    def render(self):
        match self.template:
            case str(template_str):
                return render_template_string(template_str, **self.context)
            case Path(template_path):
                return render_template(template_path, **self.context)
            case _:
                msg = "template_name or template_str must be provided"
                raise ValueError(msg)

    def enrich_context(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        new_context = deepcopy(context or {})

        if "model" in new_context:
            model = unwrap(new_context["model"])
            new_context["og_data"] = to_opengraph(model)
            new_context["json_ld"] = to_json_ld(model)

        if "json_data" not in new_context:
            new_context["json_data"] = {}

        return new_context
