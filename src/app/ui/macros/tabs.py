# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.macros import macro
from app.lib.html import a, div, nav, span


@macro
def m_tab_bar(tabs):
    return div({"class": "mb-5"}, m_tabs(tabs))


def m_tabs(tabs):
    n = len(tabs)
    tabs = [m_tab(tab, i, n) for i, tab in enumerate(tabs)]
    return nav(
        {
            "class": "relative z-0 rounded-lg shadow flex divide-x divide-gray-200",
            "_aria-label": "Tabs",
        },
        tabs,
    )


def m_tab(tab, i: int, n: int):
    class1 = (
        "uppercase tooltip tooltip-top group relative min-w-0 flex-1 overflow-hidden "
        "bg-white py-4 px-6 "
        "text-sm font-medium text-center hover:bg-gray-50 focus:z-10"
    )

    if i == 0:
        class1 += " rounded-tl-lg"

    if i == n - 1:
        class1 += " rounded-tr-lg"

    kw = {}
    if tab.get("current"):
        kw["_aria-current"] = "page"
        class1 += " text-gray-900"
    else:
        kw["_aria-current"] = "undefined"
        class1 += " text-gray-500 hover:text-gray-700"

    if tab.get("tip"):
        kw["data-tip"] = tab["tip"]

    class2 = "absolute inset-x-0 bottom-0 h-0.5"
    if tab.get("current"):
        class2 += " bg-rose-500"
    else:
        class2 += " bg-transparent"

    return a(
        {"href": tab["href"], "class": class1, **kw},
        [span(tab["label"]), span({"class": class2, "aria-hidden": "true"})],
    )
