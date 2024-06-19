# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch

from flask import render_template_string
from markdown import markdown
from markupsafe import Markup
from webbits.html import h as H  # noqa
from webbits.html import html
from wtforms import Field

from app.lib.names import to_kebab_case

# language=jinja2
TEMPLATE = """
<div class="mx-auto max-w-2xl">
    <div class="content">
        <h1>{{ step.title }}</h1>

        {% if step.subtitle %}
        <p>
            {{ step.subtitle }}
        </p>
        {% endif %}

        {% if step.preamble %}
            {{ step.preamble }}
            <hr>
        {% endif %}

        {% if step.body %}
            {{ step.body | safe }}
            <hr>
        {% endif %}
    </div>

    {% if step.form %}
        <form method="post">
        {{ step.render_buttons() }}
        {{ step.render_form() }}
        {{ step.render_buttons() }}
        </form>
    {% endif %}

    {% if step.postscript %}
        <div class="content">
            <hr/>
            {{ step.postscript }}
        </div>
    {% endif %}
</div>
"""


def get_step(step_id: str) -> Step:
    from .registry import step_registry

    return step_registry.get_step(step_id)


class Step:
    title: str
    subtitle: str = ""
    body: str = ""

    postscript_md: str = ""
    preamble_md: str = ""

    form_class = None

    next_step_id: str = ""
    prev_step: type[Step] | None = None
    is_first: bool = False

    def __init__(self):
        if self.form_class:
            self.form = self.form_class()
        else:
            self.form = None

    @property
    def id(self) -> str:
        result = to_kebab_case(self.__class__.__name__.replace("_", "-"))
        result = result.replace("--", "-")
        return result

    def get_next_step_id(self) -> str:
        """Can be overridden to dynamically determine the next step."""
        return self.next_step_id

    @property
    def is_last(self) -> bool:
        return not self.get_next_step_id()

    def render(self) -> str:
        ctx = {
            "step": self,
        }
        return render_template_string(TEMPLATE, **ctx)

    @property
    def preamble(self) -> str:
        return Markup(markdown(self.preamble_md))

    @property
    def postscript(self) -> str:
        return Markup(markdown(self.postscript_md))

    def render_form(self) -> str:
        if hasattr(self.form, "render"):
            return self.form.render()

        result = []
        for group in self.form.Meta.groups:
            result.append(self.render_group(group))

        return Markup("\n".join(result))

    def render_group(self, group) -> str:
        assert self.form

        result = [
            "<div class='my-8'><fieldset class='border border-solid border-gray-500"
            " p-4'>"
        ]

        if label := group.get("label"):
            result.append(f"<legend>{label}</legend>")

        for field_name in group["fields"]:
            field = self.form[field_name]
            result.append(self.render_field(field))

        result.append("</fieldset></div>")

        return "\n".join(result)

    def render_field(self, field: Field) -> str:
        label_class = "block text-sm font-medium leading-6 text-gray-900 mb-1"

        errors_html = H(
            "div",
            [
                H("div", error, **{"class": "text-red-600 text-sm"})
                for error in field.errors
            ],
        )
        h = html()

        with h.div({"class": "my-4 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6"}):
            h.div(
                {"class": "sm:col-span-6"},
                Markup(field.label(**{"class": label_class})),
                render_field(field),
                # Markup(field(**{"class": field_class})),
                Markup(errors_html),
            )
        return str(h)

    def render_errors(self, form) -> str:
        h = html()
        if form.errors:
            with h.div(
                {
                    "class": (
                        "bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded"
                        " relative"
                    )
                }
            ):
                h.p({"class": "font-bold"}, "Erreur")
                with h.ul({"class": "list-disc list-inside"}):
                    for field, errors in form.errors.items():
                        for error in errors:
                            h.li(f"{field.label}: {error}")
        return str(h)

    def render_buttons(self):
        prev_button = """
        <input type="submit" class="text-sm font-semibold leading-6 text-gray-900" name="_prev" value="Précédent">
        """

        next_button = """
        <input type="submit" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500" name="_next" value="Suivant">
        """

        submit_button = """
        <input type="submit" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500" name="_submit" value="Soumettre ma candidature">
        """

        h = html()
        with h.div():
            if self.is_first:
                h.div(
                    {"class": "mt-6 flex items-center justify-end gap-x-6"},
                    Markup(next_button),
                )
            elif self.is_last:
                h.div(
                    {"class": "mt-6 flex items-center justify-end gap-x-6"},
                    Markup(prev_button),
                    Markup(submit_button),
                )
            else:
                h.div(
                    {"class": "mt-6 flex items-center justify-end gap-x-6"},
                    Markup(prev_button),
                    Markup(next_button),
                )

        return Markup(str(h))


ring_class = "ring-1 ring-inset ring-gray-300"
focus_class = "focus:ring-2 focus:ring-inset focus:ring-indigo-600"
field_class = (
    "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm "
    f"placeholder:text-gray-400 sm:text-sm sm:leading-6 {ring_class} {focus_class}"
)


@singledispatch
def render_field(field: Field) -> Markup:
    return Markup(field(**{"class": field_class}))


# @render_field.register
# def render_field_bool(field: fields.BooleanField) -> Markup:
#     return "XXX"
