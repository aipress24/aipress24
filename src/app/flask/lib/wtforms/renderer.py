# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import Any

from arrow import Arrow
from attr import frozen
from case_convert import kebab_case
from flask import current_app
from markupsafe import Markup
from wtforms.fields.core import Field
from wtforms.form import Form

# language=jinja2
FORM_TEMPLATE = """
{% if form.errors %}
    <div class="alert alert-error">Erreurs dans le formulaire</div>

    <ul class="errors">
        {% for field_name, field_errors in form.errors|dictsort if field_errors %}
            {% for error in field_errors %}
                <li>{{ form[field_name].label }}: {{ error }}</li>
            {% endfor %}
        {% endfor %}
    </ul>
{% endif %}

<form
    class="aip-form flex flex-col space-y-6 divide-y divide-gray-200"
    action="{{ renderer.action_url }}"
    method="post"
    enctype="multipart/form-data"
>
  {% if model %}
    <input type="hidden" name="id" value="{{ model.id }}"/>
  {% endif %}

  {% for group in groups %}
    {{ renderer.render_group(group) }}
  {% endfor %}

  <div class="pt-5">
    <div class="flex justify-end">
      <button
          name="_action" value="cancel" type="submit"
          class="button ~neutral">
        Annuler
      </button>

      <button
          name="_action" value="submit" type="submit"
          class="ml-4 button ~info @high">
        Enregistrer
      </button>
    </div>
  </div>
</form>
"""

# language=jinja2
GROUP_TEMPLATE = """
  <div class="flex flex-col py-6 space-y-6">
    {% if group.label %}
      <h3 class="text-2xl mt-4 leading-6 font-medium text-gray-900">{{ group.label }}</h3>
    {% endif %}

    <div class="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6">
      {% for field in group.fields %}
        {{ renderer.render_field(field) }}
      {% endfor %}
    </div>
  </div>
"""

# language=html
FIELD_TEMPLATE = """
{% if errors %}
    {% set error_class = "text-red-500" %}
{% else %}
    {% set error_class = "" %}
{% endif %}

<div class="sm:col-span-{{ width }}">
  <label for="{{ id }}" class="dui-label">
    <span class="aui-label-text {{error_class}}">{{ label }}</span>
    {% if errors %}
        <div class="text-red-500 text-sm">{{ errors[0] }}</div>
    {% endif %}
  </label>

  <div class="rounded-md shadow-sm">
    {{ field }}
  </div>
</div>
"""

#
# mode=view
#

# language=jinja2
FORM_VIEW_TEMPLATE = """
<div class="aip-form flex flex-col space-y-6 divide-y divide-gray-200">
  {% for group in groups %}
    {{ renderer.render_group(group) }}
  {% endfor %}

  <div class="pt-5">
    <div class="flex justify-end">
      <a href=".."
          class="button ~neutral">
        Retour
      </a>
    </div>
  </div>
</div>
"""

# language=jinja2
GROUP_VIEW_TEMPLATE = """
  <div class="flex flex-col py-6 space-y-6">
    {% if group.label %}
      <h3 class="text-2xl mt-4 leading-6 font-medium text-gray-900">{{ group.label }}</h3>
    {% endif %}

    <div class="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6">
      {% for field in group.fields %}
        {{ renderer.render_field(field) }}
      {% endfor %}
    </div>
  </div>
"""

# language=html
FIELD_VIEW_TEMPLATE = """
<div class="sm:col-span-{{ width }}">
  <label for="{{ id }}" class="dui-label">
    <span class="aui-label-text">{{ label }}</span>
  </label>

  <div class="rounded-md shadow-sm">
    {{ field }}
  </div>
</div>
"""


FIELD_CLASS_MAP = {
    "default": "dui-input dui-input-bordered w-full",
    "select": "dui-select dui-select-bordered w-full",
    "date-time": (
        "shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full"
        " sm:text-sm border-gray-300 rounded-md"
    ),
    "date": (
        "shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full"
        " sm:text-sm border-gray-300 rounded-md"
    ),
    # "text-area": "rich-text",
}

DEFAULT_WIDTH = 6


@frozen
class FormRenderer:
    form: Form
    model: Any = None
    mode: str = "view"
    action_url: str = ""

    _type = "ignore"

    def render(self) -> Markup:
        groups = self.get_groups()

        if self.mode == "view":
            template = current_app.jinja_env.from_string(FORM_VIEW_TEMPLATE)
        else:
            template = current_app.jinja_env.from_string(FORM_TEMPLATE)
        ctx = {
            "groups": groups,
            "form": self.form,
            "model": self.model,
            "renderer": self,
        }
        return Markup(template.render(**ctx).strip())

    def render_group(self, group) -> str:
        if self.mode == "view":
            template = current_app.jinja_env.from_string(GROUP_VIEW_TEMPLATE)
        else:
            template = current_app.jinja_env.from_string(GROUP_TEMPLATE)
        ctx = {
            "group": group,
            "renderer": self,
        }
        return Markup(template.render(**ctx).strip())

    def render_field(self, field: Field) -> str:
        field_type_key = kebab_case(field.__class__.__name__)
        if field_type_key not in FIELD_CLASS_MAP:
            field_type_key = "default"
        class_ = FIELD_CLASS_MAP[field_type_key]
        if field.errors:
            class_ += " input-error"

        if self.mode == "view":
            field_str = self.render_field_value(field.data)
        else:
            field_str = field(**{"class": class_})

        if field.render_kw:
            width = field.render_kw.get("width", DEFAULT_WIDTH)
        else:
            width = DEFAULT_WIDTH

        ctx = {
            "id": field.id,
            "label": field.label.text,
            "field": Markup(field_str),
            "errors": field.errors,
            "width": width,
        }

        if self.mode == "view":
            template = current_app.jinja_env.from_string(FIELD_VIEW_TEMPLATE)
        else:
            template = current_app.jinja_env.from_string(FIELD_TEMPLATE)
        return Markup(template.render(**ctx).strip())

    def get_groups(self):
        groups_spec = self.form.Meta.groups  # type: ignore
        groups = []
        for group_id, _group in groups_spec.items():
            group = _group.copy()
            group["id"] = group_id
            group["fields"] = []
            for field_id in _group["fields"]:
                group["fields"].append(self.form[field_id])
            groups.append(group)
        return groups

    def render_field_value(self, value: Any):
        match value:
            case None:
                return ""
            case bool():
                return "Oui" if value else "Non"
            case str():
                return value
            case datetime():
                return value.strftime("%d/%m/%Y à %H:%M")
            case Arrow():
                return value.strftime("%d/%m/%Y à %H:%M")
            case _:
                return str(value)
