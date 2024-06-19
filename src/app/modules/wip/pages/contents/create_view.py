# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import webargs
from flask import g, redirect, request, url_for
from sqlalchemy_utils.types.arrow import arrow
from werkzeug.datastructures import ImmutableMultiDict

from app.flask.components.forms import Form
from app.flask.extensions import db
from app.models.content import BaseContent

from ...models.newsroom.article import ArticleStatus
from .base_view import View
from .constants import DOC_CLASSES

# language=jinja2
CREATE_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  <h2 class="max-w-6xl mx-auto mt-8 text-lg leading-6 font-medium text-gray-900">
    {{ form_rendered|safe }}
  </h2>
{% endblock %}
"""


class CreateView(View):
    ARGS = {
        "doc_type": webargs.fields.Str(load_default=None),
    }

    def context_for_get(self):
        options = self._get_options()
        assert self.form
        form_rendered = self.form.render()
        return {
            "title": f'Créer un document de type "{self.doc_type}"',
            "_template_str": CREATE_TEMPLATE,
            "options": options,
            "form": self.form,
            "form_rendered": form_rendered,
        }

    def context_for_post(self):
        doc_type = self.args["doc_type"]
        form = self._get_form(doc_type)
        new_doc = self._create_doc(form, request.form)

        # TEMP
        new_doc.published_at = arrow.now("Europe/Paris")
        new_doc.status = ArticleStatus.PUBLIC
        if g.user.organisation_id:
            new_doc.publisher_id = g.user.organisation_id

        db.session.add(new_doc)
        db.session.commit()
        return redirect(url_for(".contents"))

    def _create_doc(self, form: Form, data: ImmutableMultiDict) -> BaseContent:
        doc_type = form._type

        doc_class = DOC_CLASSES[doc_type]

        doc = doc_class()
        doc.owner = g.user
        doc.status = "draft"

        for field in form.fields.values():
            # debug(field)
            field_id = field["id"]
            value = data.get(field_id)
            if field_id == "language":
                continue
            setattr(doc, field_id, value)

        return doc
