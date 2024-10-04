# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Response, request
from webargs.flaskparser import parser
from werkzeug.exceptions import BadRequest, NotFound

import app.settings.vocabularies as voc
from app.flask.components.forms import Form, get_form_specs
from app.flask.sqla import get_obj
from app.lib.names import to_kebab_case
from app.models.content import BaseContent


class View:
    ARGS: dict[str, Any] = {}
    args: Mapping[str, Any]
    doc_type: str = ""
    form: Form | None = None
    model: Any = None

    def __init__(self):
        self.args = parser.parse(self.ARGS, request, location="query")
        assert self.args is not None
        if model_id := self.args.get("id"):
            self.model = get_obj(model_id, BaseContent)
            self.doc_type = to_kebab_case(self.model.__class__.__name__)
        else:
            self.doc_type = self.args.get("doc_type")
        if self.doc_type:
            self.form = self._get_form(self.doc_type)
        # if self.form and self.model:
        #     self.form.set_model(self.model)

    def context(self):
        method = request.method

        match method:
            case "GET":
                return self.context_for_get()
            case "POST":
                return self.context_for_post()
            case _:
                raise NotFound(f"Method {method} not available")

    def post(self):
        return

    def context_for_get(self) -> Mapping[str, Any]:
        """Context for GET methods."""
        raise NotImplementedError

    def context_for_post(self) -> Mapping[str, Any] | Response:
        """Context for POST methods."""
        raise NotImplementedError

    def _get_form(self, doc_type: str) -> Form:
        if "/" in doc_type:
            raise BadRequest
        if ".." in doc_type:
            raise BadRequest
        doc_type = doc_type.replace(":", "/")

        file = f"{doc_type}.toml"
        form_specs = get_form_specs(file)
        if self.model:
            form = Form(form_specs, self.model)
        else:
            form = Form(form_specs)
        form._type = doc_type
        return form

    def _get_options(self):
        return {
            "genres": voc.get_genres(),
            "topics": voc.get_topics(),
            "sections": voc.get_sections(),
            "news_sectors": voc.get_news_sectors(),
            "locations": ["TODO"],
        }

    def _get_template(self):
        file = inspect.getfile(self.__class__)
        path = Path(file)
        template = path.with_suffix(".j2")
        return template.read_text()
