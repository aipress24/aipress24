# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# import importlib
# from collections.abc import Generator
# from types import ModuleType
#
# from flask import current_app, redirect, render_template, request
# from jinja2 import Environment
# from markupsafe import Markup
# from webbits.html import h as H
# from webbits.html import html
#
# from app.flask.routing import url_for
# from app.modules.kyc import get
# from app.modules.kyc.wizards.base import WizardStep
#
#
# @get("/wizard/")
# def wizard():
#     step = get_first_step()
#     return redirect(url_for(".wizard_step", step_id=step.id))
#
#
# # language=jinja2
# template = """
# <div class="mx-auto max-w-2xl content">
#     <h1 class="">{{ title }}</h1>
#
#     <p class="font-bold text-lg mt-2 mb-4">{{ step.title }}</p>
#
#     {% if step.preamble %}
#         {{ step.preamble }}
#         <hr>
#     {% endif %}
#
#     <ul>
#     {% for child in children %}
#         <li class="mb-4">
#             <a href="{{ url_for(".wizard_step", step_id=child.id) }}">{{ child.title }}</a>
#         </li>
#     {% endfor %}
#     </ul>
#
#     {% if step.questions %}
#     <ul>
#         {% for question in step.questions %}
#         <li class="mb-4">{{ question }}</li>
#         {% endfor %}
#     </ul>
#     {% endif %}
#
#     {% if step.postscript %}
#         <hr/>
#         {{ step.postscript }}
#     {% endif %}
#
#     {{ buttons }}
# </div>
# """
#
#
# @get("/wizard/<step_id>")
# def wizard_step(step_id):
#     steps = list(get_steps())
#     step = get_step(step_id)
#
#     if request.args.get("_prev"):
#         prev_step_id = step.previous_step_id
#         return redirect(url_for(".wizard_step", step_id=prev_step_id))
#
#     children = []
#     for _step in steps:
#         if _step.previous_step_id == step_id:
#             children.append(_step)
#
#     title = "Inscription sur Aipress24"
#
#     jinja_env: Environment = current_app.jinja_env
#     _ctx = {
#         "title": title,
#         "step": step,
#         "children": children,
#         "buttons": render_buttons(step),
#     }
#     content = jinja_env.from_string(template).render(**_ctx)
#
#     # content = H(
#     #     "div",
#     #     {"class": "mx-auto max-w-2xl"},
#     #     [
#     #         H("h1", title, **{"class": "font-bold text-2xl mb-4"}),
#     #
#     #         H("h2", step.title, **{"class": "font-bold text-xl mb-4"}),
#     #         # form_html,
#     #         # [
#     #         #     H("div", child.title, **{"class": "font-bold text-xl mb-4"})
#     #         #     for child in children
#     #         # ]
#     #         H("p", "TODO"),
#     #         ["Hello", "world"],
#     #     ],
#     # )
#
#     ctx = {
#         "title": title,
#         "content": content,
#     }
#     return render_template("kyc/_layout.html", **ctx)
#
#
# def render_buttons(step):
#     # prev_button = H(
#     #     "input",
#     #     **{
#     #         "type": "submit",
#     #         "class": "text-sm font-semibold leading-6 text-gray-900",
#     #         "name": "_prev",
#     #         "value": "Précédent",
#     #     },
#     # )
#
#     # next_button = H(
#     #     "input",
#     #     **{
#     #         "type": "submit",
#     #         "class": "inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
#     #         "name": "_next",
#     #         "value": "Suivant",
#     #     },
#     # )
#
#     # submit_button = H(
#     #     "input",
#     #     **{
#     #         "type": "submit",
#     #         "class": "inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
#     #         "name": "_submit",
#     #         "value": "Soumettre ma candidature",
#     #     },
#     # )
#
#     prev_button = """
#     <input type="submit" class="text-sm font-semibold leading-6 text-gray-900" name="_prev" value="Précédent">
#     """
#
#     submit_button = """
#     <input type="submit" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500" name="_submit" value="Soumettre ma candidature">
#     """
#
#     h = html()
#     with h.form():
#         if step.is_first:
#             pass
#             # h.div(
#             #     {"class": "mt-6 flex items-center justify-end gap-x-6"},
#             #     Markup(next_button),
#             # )
#         elif step.is_end:
#             h.div(
#                 {"class": "mt-6 flex items-center justify-end gap-x-6"},
#                 Markup(prev_button),
#                 Markup(submit_button),
#             )
#         else:
#             h.div(
#                 {"class": "mt-6 flex items-center justify-end gap-x-6"},
#                 Markup(prev_button),
#                 # Markup(next_button),
#             )
#
#     return Markup(str(h))
#
#
# def get_step(step_id) -> WizardStep:
#     steps = get_steps()
#     for step in steps:
#         if step.id == step_id:
#             return step
#     raise KeyError(f"No step found with id {step_id}")
#
#
# def get_first_step() -> WizardStep:
#     steps = get_steps()
#     for step in steps:
#         if step.is_first:
#             return step
#     raise ValueError("No first step found")
#
#
# def get_steps() -> Generator[WizardStep, None, None]:
#     wizard_module = importlib.import_module("app.modules.kyc.wizards")
#     for obj in vars(wizard_module).values():
#         if not isinstance(obj, ModuleType):
#             continue
#         module = obj
#         for obj1 in vars(module).values():
#             if isinstance(obj1, type) and issubclass(obj1, WizardStep):
#                 # Skip the base class
#                 if obj1 is WizardStep:
#                     continue
#                 step = obj1()
#                 yield step
