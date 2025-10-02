# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any, ClassVar

from attr import frozen

from app.flask.lib.macros import macro
from app.flask.lib.pywire import Component, component
from app.lib.html import a, div, nav, span
from app.ui.macros.icon import icon

from .biz_card import BizCard

BUTTONS = """
<span class="relative z-0 inline-flex shadow-sm">
  <button type="button"
    class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
    @click="showFilters = !showFilters">
    {icon_filter}
  </button>

  <button type="button"
    class="-ml-px relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
    @click="showSorter = !showSorter">
    {icon_sort}
  </button>
</span>
"""


@component
@frozen
class BizTabs(Component):
    tabs: list[Any]
    components: ClassVar = [BizCard]

    def __call__(self):
        # debug(self)
        result = m_tab_bar(self.tabs)
        return result
        # context = self.__get_context()
        # template = self.__get_template()

        # # There is a type declaration error in Flask
        # return Markup(render_template(template, **context))

    # def __get_context(self):
    #     context = {}
    #     for attr in dir(self):
    #         if attr.startswith("_"):
    #             continue
    #         context[attr] = getattr(self, attr)
    #     return context
    #
    # def __get_template(self) -> Template:
    #     template_name = to_snake_case(self.__class__.__name__) + ".j2"
    #     template_file = Path(inspect.getfile(self.__class__)).parent / template_name
    #     jinja_env: Environment = current_app.jinja_env
    #     return jinja_env.from_string(template_file.open().read())


@macro
def m_tab_bar(tabs):
    # return m_tabs(tabs)
    icon_filter = icon("funnel", _class="h-5 w-5")
    icon_sort = icon("bars-arrow-down", _class="h-5 w-5")
    buttons = BUTTONS.format(**locals())
    return div(
        {"class": "mb-5"},
        div(
            {"class": "flex justify-between items-end"},
            [
                div({"class": "flex-grow mr-4"}, m_tabs(tabs)),
                div({"class": "text-gray-600"}, buttons),
            ],
        ),
    )


def m_tabs(tabs):
    n = len(tabs)
    tabs = [m_tab(tab, i, n) for i, tab in enumerate(tabs)]
    return nav(
        {
            "class": "relative z-0 rounded-lg shadow flex divide-x divide-gray-200",
            "aria-label": "Tabs",
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
