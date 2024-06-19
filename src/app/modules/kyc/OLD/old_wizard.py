# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# from flask import redirect, render_template, request, session, url_for
# from markupsafe import Markup
# from sqlalchemy import select
# from webbits.html import h as H
# from webbits.html import html
# from werkzeug import Response
# from wtforms import Field
#
# from app.flask.extensions import db
#
# from .. import get, route
# from ..forms import BaseForm, Step1Form, Step2Form, Step3Form
# from ..models import MembershipApplication
#
# FORMS = [Step1Form, Step2Form, Step3Form]
#
#
# @route("/<int:step>", methods=["GET", "POST"])
# @route("/", methods=["GET", "POST"])
# def step(step: int = 0) -> Response | str:
#     form_data = request.form
#     mapp_id = session.get("mapp_id")
#     if mapp_id:
#         stmt = select(MembershipApplication).where(MembershipApplication.id == mapp_id)
#         mapp = db.session.execute(stmt).scalar_one()
#     else:
#         mapp = MembershipApplication()
#     if mapp.data is None:
#         mapp.data = {}
#
#     form = FORMS[step](form_data, meta={"csrf": False})
#
#     if request.method == "POST" and form.validate():
#         # Update the mapp with the form data
#         mapp_data = mapp.data
#         for name, field in form._fields.items():
#             mapp_data[name] = field.data
#         mapp.data = mapp_data
#
#         db.session.add(mapp)
#         db.session.commit()
#         session["mapp_id"] = mapp.id
#
#         if request.form.get("_submit"):
#             return redirect(url_for("kyc.confirm"))
#
#         if request.form.get("_next"):
#             step += 1
#         elif request.form.get("_prev"):
#             step -= 1
#
#         return redirect(url_for("kyc.step", step=step))
#
#     for name, data in mapp.data.items():
#         if name in form._fields:
#             field: Field = form._fields[name]
#             field.data = data
#
#     title = "Inscription"
#     form_html = render_form(form)
#     content = H(
#         "div",
#         [
#             H("h1", title, **{"class": "font-bold text-2xl mb-4"}),
#             form_html,
#         ],
#         **{"class": "mx-auto max-w-2xl"},
#     )
#     ctx = {
#         "title": title,
#         "content": content,
#     }
#     return render_template("kyc/_layout.html", **ctx)
#
#
# @get("/confirm/")
# def confirm() -> str:
#     title = "Confirmation"
#     content = H(
#         "div",
#         [
#             H(
#                 "h1",
#                 "Merci pour votre inscription !",
#                 **{"class": "text-3xl font-extrabold leading-9 text-gray-900"},
#             ),
#             H("p", "Nous allons étudier votre candidature avec soin."),
#             H("p", "Vous allez recevoir un email de confirmation."),
#         ],
#         **{"class": "content"},
#     )
#
#     ctx = {
#         "title": title,
#         "content": content,
#     }
#     return render_template("kyc/_layout.html", **ctx)
#
#
# def render_form(form: BaseForm) -> str:
#     h2_class = "text-base font-semibold leading-7 text-gray-900"
#
#     prev_button = H(
#         "input",
#         **{
#             "type": "submit",
#             "class": "text-sm font-semibold leading-6 text-gray-900",
#             "name": "_prev",
#             "value": "Précédent",
#         },
#     )
#
#     next_button = H(
#         "input",
#         **{
#             "type": "submit",
#             "class": "inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
#             "name": "_next",
#             "value": "Suivant",
#         },
#     )
#
#     submit_button = H(
#         "input",
#         **{
#             "type": "submit",
#             "class": "inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
#             "name": "_submit",
#             "value": "Soumettre ma candidature",
#         },
#     )
#
#     h = html()
#     with h.form({"method": "POST"}, action=""):
#         # render_errors(h, form)
#
#         h.h2(form._meta["title"], {"class": h2_class})
#
#         for field in form:
#             render_field(h, field)
#
#         if form._meta["step"] == 1:
#             h.div(
#                 {"class": "mt-6 flex items-center justify-end gap-x-6"},
#                 Markup(next_button),
#             )
#         elif form._meta["step"] == 3:
#             h.div(
#                 {"class": "mt-6 flex items-center justify-end gap-x-6"},
#                 Markup(prev_button),
#                 Markup(submit_button),
#             )
#         else:
#             h.div(
#                 {"class": "mt-6 flex items-center justify-end gap-x-6"},
#                 Markup(prev_button),
#                 Markup(next_button),
#             )
#
#     return str(h)
#
#
# def render_field(h, field: Field):
#     label_class = "block text-sm font-medium leading-6 text-gray-900 mb-1"
#
#     ring_class = "ring-1 ring-inset ring-gray-300"
#     focus_class = "focus:ring-2 focus:ring-inset focus:ring-indigo-600"
#     field_class = f"block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm  placeholder:text-gray-400 sm:text-sm sm:leading-6 {ring_class} {focus_class}"
#
#     errors_html = H(
#         "div",
#         [
#             H("div", error, **{"class": "text-red-600 text-sm"})
#             for error in field.errors
#         ],
#     )
#
#     with h.div({"class": "mt-10 grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-6"}):
#         h.div(
#             {"class": "sm:col-span-6"},
#             Markup(field.label(**{"class": label_class})),
#             Markup(field(**{"class": field_class})),
#             Markup(errors_html),
#         )
#
#
# def render_errors(h, form):
#     if form.errors:
#         with h.div(
#             {
#                 "class": "bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative"
#             }
#         ):
#             h.p({"class": "font-bold"}, "Erreur")
#             with h.ul({"class": "list-disc list-inside"}):
#                 for field, errors in form.errors.items():
#                     for error in errors:
#                         h.li(f"{field.label}: {error}")
