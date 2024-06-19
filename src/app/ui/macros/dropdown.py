# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Useful macros, written in Python."""

from __future__ import annotations

template = """
  <div
      x-data="{
        open: false,
        toggle() {
            if (this.open) {
                return this.close();
            }
            this.open = true;
        },
        close(focusAfter) {
            this.open = false;
            focusAfter && focusAfter.focus();
        }
    }"
      x-on:keydown.escape.prevent.stop="close($refs.button)"
      x-on:focusin.window="! $refs.panel.contains($event.target) && close()"
      x-id="['dropdown-button']"
      class="relative"
  >
    <button
        type="button"
        aria-haspopup="true"
        aria-expanded="false"
        class="bg-white p-2 rounded-full text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
        x-ref="button"
        x-on:click="toggle()"
        :aria-expanded="open"
        :aria-controls="$id('dropdown-button')"
    >
      <span class="sr-only">Open user menu</span>
      {{ icon(icon_name, type="outline", class="h-6 w-6") }}
    </button>

    <!-- Panel -->
    <div
        x-ref="panel"
        x-show="open"
        x-transition.origin.top.left
        x-on:click.outside="close($refs.button)"
        :id="$id('dropdown-button')"
        style="display: none"
        class="absolute z-20 right-0 mt-2 bg-white border border-gray-200 rounded shadow-lg"
    >
      {{ caller() }}
    </div>
  </div>
"""

# def dropdown(icon_name) -> None:
#     return


# @macro
# def toto(*args, **kw):
#     debug(args)
#     debug(kw)
#     caller = kw.get("caller")
#     if not caller:
#         return
#
#     debug(vars(caller))
#     debug(caller._func())
#     return ""


#
# class Component:
#     pass
#
#
# class Header(Component):
#     pass
#
#
# class MenuBar(Component):
#     pass
#
#
# @define
# class MainMenu(Component):
#     menu_items: list

# def __call__(self):
#     items = [
#         html("""
#             <a href="{item.url}"
#                 class="tooltip tooltip-bottom text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium"
#                 aria-current="page" data-tip="{item.tooltip}"
#             >{item.label}</a>
#         """)
#         for item in self.menu_items
#     ]
#     return html("""
#         <div class="hidden sm:-my-px sm:ml-6 sm:flex sm:space-x-8">
#             {items}
#         </div>
#     """)

# def __html__(self):
#     return h(
#         "div",
#         class_="hidden sm:-my-px sm:ml-6 sm:flex sm:space-x-8",
#         children=[
#             h(
#                 "a",
#                 **{
#                     "href": item.url,
#                     "class": "tooltip tooltip-bottom text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium",
#                     "aria-current": "page",
#                     "data-tip": item.tooltip,
#                 },
#                 children=item.label,
#             )
#             for item in self.menu_items
#         ],
#     ).pretty()


# if __name__ == "__main__":
#     item = {
#         "url": "http://example/com",
#         "tooltip": "toto",
#         "label": "titi",
#     }
#
#     c = MainMenu([item])
#     print(c())
#     print(render(c()))
