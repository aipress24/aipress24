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
DETAIL_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  <h2 class="max-w-6xl mx-auto mt-8 text-lg leading-6 font-medium text-gray-900">
    {{ obj.title }}
  </h2>

  {% for field in form.fields.values() %}
    <h3 class="mt-8 mb-4 text-lg font-bold">
      {{ field.label }}
    </h3>
    <div class="mb-8">
      {{ field.render_view() }}
    </div>
  {% endfor %}
{% endblock %}
"""


class DetailView(View):
    ARGS = {
        "id": webargs.fields.Str(load_default=None),
        "doc_type": webargs.fields.Str(load_default=None),
    }

    def get_context(self):
        type_label = get_label(self.model)
        title = f"{type_label}: {self.model.title}"
        breadcrumbs = [
            BreadCrumb(
                url=url_for("wip.contents", mode="list"), label="Liste des contenus"
            ),
        ]
        return {
            "_template_str": DETAIL_TEMPLATE,
            "obj": self.model,
            "title": title,
            "form": self.form,
            "breadcrumbs2": breadcrumbs,
        }
