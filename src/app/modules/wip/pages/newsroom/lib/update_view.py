# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import webargs
from flask import url_for

from app.flask.lib.breadcrumbs import BreadCrumb
from app.models.meta import get_label

from .base_view import View

# language=jinja2
UPDATE_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  <h2 class="max-w-6xl mx-auto mt-8 text-lg leading-6 font-medium text-gray-900">
    {{ form_rendered|safe }}
  </h2>
{% endblock %}
"""


class UpdateView(View):
    ARGS = {
        "id": webargs.fields.Str(load_default=None),
    }

    def get_context(self):
        type_label = get_label(self.model)
        title = f'Modifier le contenu: "{self.model.title}" ({type_label})'

        assert self.form
        form_rendered = self.form.render()
        breadcrumbs = [
            BreadCrumb(
                url=url_for("wip.contents", mode="list"), label="Liste des contenus"
            ),
        ]

        return {
            "_template_str": UPDATE_TEMPLATE,
            "title": title,
            "obj": self.model,
            "options": self._get_options(),
            "form": self.form,
            "form_rendered": form_rendered,
            "breadcrumbs2": breadcrumbs,
        }

    def post_context(self):
        return {}
