# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from flask import Response, current_app, render_template, render_template_string
from jinja2 import Template

from app.flask.lib.view_model import unwrap
from app.services.json_ld import to_json_ld
from app.services.opengraph import to_opengraph


def resolve_template_path(obj: Any, path: str) -> Path:
    """Return the on-disk template path for ``obj`` and ``path``.

    Pure: given the same inputs, returns the same path. No I/O.
    """
    try:
        file = Path(inspect.getfile(obj))
    except TypeError:
        file = Path(inspect.getfile(obj.__class__))
    if path:
        return file.parent / path
    return file.with_suffix(".j2")


def get_related_template(obj: Any, path: str) -> Template:
    template_file = resolve_template_path(obj, path)
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
            case Path() as template_path:
                return render_template(str(template_path), **self.context)
            case _:
                msg = "template_name or template_str must be provided"
                raise ValueError(msg)

    def enrich_context(
        self,
        context: dict[str, Any] | None = None,
        *,
        to_opengraph_fn: Callable[[Any], dict] | None = None,
        to_json_ld_fn: Callable[[Any], Any] | None = None,
    ) -> dict[str, Any]:
        return enrich_context(
            context,
            to_opengraph_fn=to_opengraph_fn,
            to_json_ld_fn=to_json_ld_fn,
        )


def enrich_context(
    context: dict[str, Any] | None = None,
    *,
    to_opengraph_fn: Callable[[Any], dict] | None = None,
    to_json_ld_fn: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Return a new enriched context dict.

    Pure: no Flask globals; collaborators may be injected for tests.
    Defaults preserve production behavior (calls the real services).
    """
    og_fn = to_opengraph_fn if to_opengraph_fn is not None else to_opengraph
    jld_fn = to_json_ld_fn if to_json_ld_fn is not None else to_json_ld

    new_context = deepcopy(context or {})

    if "model" in new_context:
        model = unwrap(new_context["model"])
        new_context["og_data"] = og_fn(model)
        new_context["json_ld"] = jld_fn(model)

    if "json_data" not in new_context:
        new_context["json_data"] = {}

    return new_context
