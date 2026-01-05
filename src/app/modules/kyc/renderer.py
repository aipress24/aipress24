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

ring_class = "ring-1 ring-inset ring-gray-300"
focus_class = "focus:ring-2 focus:ring-inset focus:ring-indigo-600"
ring_class_ro = "ring-1 ring-inset ring-gray-100"
focus_class_ro = "focus:ring-0 focus:ring-inset focus:ring-gray-100"

DEFAULT_CSS = (
    "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm "
    "placeholder:text-gray-400 sm:text-sm sm:leading-6 "
    f"{ring_class} {focus_class}"
)
DEFAULT_CSS_RO = (
    "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm "
    "placeholder:text-gray-400 sm:text-sm sm:leading-6 "
    f"{ring_class_ro} {focus_class_ro}"
)
CSS_CLASS = {
    "boolean": (
        "w-4 h-4 border-2 border-blue-500 rounded-sm bg-white mt-1 "
        "shrink-0 checked:bg-blue-800 checked:border-2"
    ),
    "string": DEFAULT_CSS,
    "photo": DEFAULT_CSS,
    "email": DEFAULT_CSS,
    "tel": DEFAULT_CSS,
    "password": DEFAULT_CSS,
    "code": DEFAULT_CSS,
    "url": DEFAULT_CSS,
}

CSS_CLASS_RO = {
    "boolean": (
        "w-4 h-4 border-2 border-gray-500 rounded-sm bg-white mt-1 "
        "checked:bg-gray-800 checked:border-2"
    ),
    "string": DEFAULT_CSS_RO,
    "photo": DEFAULT_CSS_RO,
    "email": DEFAULT_CSS_RO,
    "tel": DEFAULT_CSS_RO,
    "password": DEFAULT_CSS_RO,
    "code": DEFAULT_CSS_RO,
    "url": DEFAULT_CSS_RO,
}


def render_field(field) -> str:
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


def _upper_message(field) -> str:
    render_kw = getattr(field, "render_kw", {}) or {}
    return (render_kw.get("kyc_message") or "").strip()


def _field_type(field) -> str:
    render_kw = getattr(field, "render_kw", {}) or {}
    return render_kw.get("kyc_type", "string")


def _is_mandatory_field(field) -> bool:
    render_kw = getattr(field, "render_kw", {})
    return render_kw.get("kyc_code", "") == "M"


# def mandatory_filter_label(field: Field, css_class: str) -> str:
#     if _is_mandatory_field(field):
#         return Markup(field.label(**{"class": css_class}) + "(*)")
#     else:
#         return Markup(field.label(**{"class": css_class}))


@singledispatch
def _render_field(field) -> Markup:
    render_kw = getattr(field, "render_kw", {}) or {}
    readonly = render_kw.get("readonly", "")

    if readonly:
        css_class = CSS_CLASS_RO.get(_field_type(field), DEFAULT_CSS_RO)
    else:
        css_class = CSS_CLASS.get(_field_type(field), DEFAULT_CSS)

    return Markup(field(**{"class": css_class}))
