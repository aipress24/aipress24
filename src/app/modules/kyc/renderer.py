# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from functools import singledispatch

from markupsafe import Markup
from webbits.html import (
    h as H,  # noqa
    html,
)
from wtforms.fields.core import Field

ring_class = "ring-1 ring-inset ring-gray-300"
focus_class = "focus:ring-2 focus:ring-inset focus:ring-indigo-600"
field_class = (
    f"block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm "
    f"placeholder:text-gray-400 sm:text-sm sm:leading-6 {ring_class} {focus_class}"
)
DEFAULT_CSS = field_class
CSS_CLASS = {
    "boolean": (
        "w-4 h-4 border-2 border-blue-500 rounded-sm bg-white mt-1 "
        "shrink-0 checked:bg-blue-800 checked:border-2"
    ),
    "string": field_class,
    "photo": DEFAULT_CSS,
    "email": DEFAULT_CSS,
    "tel": DEFAULT_CSS,
    "password": DEFAULT_CSS,
    "code": DEFAULT_CSS,
    "url": DEFAULT_CSS,
}


def render_field(field: Field) -> str:
    upper_message_class = "block text-sm font-medium leading-7 text-gray-900 mb-1 mt-1"
    label_class = "block text-sm font-medium leading-6 text-gray-900 mb-1"
    label_right_class = "text-sm font-medium leading-6 text-gray-900 ml-2"

    errors_html = H(
        "div",
        [
            H("div", error, **{"class": "text-red-600 text-sm"})
            for error in field.errors
        ],
    )
    h = html()

    if upper_message := _upper_message(field):
        h.div({"class": upper_message_class}, upper_message)

    if _field_type(field) == "boolean":
        # put widget before label
        with h.div({"class": "my-4"}):
            h.div(
                {"class": "sm:col-span-6"},
                _render_field(field),
                Markup(field.label(**{"class": label_right_class})),
                Markup(errors_html),
            )
    else:
        with h.div({"class": "my-4 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6"}):
            h.div(
                {"class": "sm:col-span-6"},
                Markup(field.label(**{"class": label_class})),
                _render_field(field),
                Markup(errors_html),
            )
    return Markup(str(h))


def _upper_message(field: Field) -> str:
    render_kw = getattr(field, "render_kw", {}) or {}
    return (render_kw.get("kyc_message") or "").strip()


def _field_type(field: Field) -> str:
    render_kw = getattr(field, "render_kw", {}) or {}
    return render_kw.get("kyc_type", "string")


def _is_mandatory_field(field: Field) -> bool:
    render_kw = getattr(field, "render_kw", {})
    return render_kw.get("kyc_code", "") == "M"


# def mandatory_filter_label(field: Field, css_class: str) -> str:
#     if _is_mandatory_field(field):
#         return Markup(field.label(**{"class": css_class}) + "(*)")
#     else:
#         return Markup(field.label(**{"class": css_class}))


@singledispatch
def _render_field(field: Field) -> Markup:
    css_class = CSS_CLASS.get(_field_type(field), DEFAULT_CSS)

    return Markup(field(**{"class": css_class}))
