# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from devtools import debug
from flask import g, request, url_for
from flask_login import current_user
from flask_security import ChangePasswordForm
from werkzeug import Response
from werkzeug.utils import redirect
from wtforms.form import Form

from app.flask.extensions import db
from app.flask.lib.pages import page

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefPasswordPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "password"
    label = "Mot de passe"
    icon = "key"
    template = "pages/preferences/password.j2"

    def context(self) -> dict[str, Any] | Response:
        form = ChangePasswordForm()
        return {
            "form": form,
            "active_password": True if current_user.password else False,
        }


    def post(self):
        debug(dict(request.form))

        # if not current_user.is_authenticated:
        #     msg = "No currently authenticated user"
        #     raise ValueError(msg)
        # if request.form.get("submit") == "cancel":
        #     return redirect(url_for(f".{self.name}"))
        #
        # response = {}
        # for key, val in request.form.items():
        #     response[key] = val
        # # search hobbies response
        # new_hobbies = response.get("hobbies")
        # if not new_hobbies:
        #     return redirect(url_for(f".{self.name}"))
        # user = g.user
        # profile = user.profile
        # profile.set_value("hobbies", new_hobbies)
        # db_session = db.session
        # db_session.merge(user)
        # db_session.commit()

        return redirect(self.url)



# @auth_required(lambda: cv("API_ENABLED_METHODS"))
# def change_password():
#     """View function which handles a change password request."""
#     form = t.cast(ChangePasswordForm, build_form_from_request("change_password_form"))
#
#     if not current_user.password:
#         # This is case where user registered w/o a password - since we can't
#         # confirm with existing password - make sure fresh using whatever authentication
#         # method they have set up.
#         if not check_and_update_authn_fresh(
#             cv("FRESHNESS"),
#             cv("FRESHNESS_GRACE_PERIOD"),
#             get_request_attr("fs_authn_via"),
#         ):
#             return _security._reauthn_handler(
#                 cv("FRESHNESS"), cv("FRESHNESS_GRACE_PERIOD")
#             )
#
#     if form.validate_on_submit():
#         after_this_request(view_commit)
#         change_user_password(current_user._get_current_object(), form.new_password.data)
#         if _security._want_json(request):
#             form.user = current_user
#             return base_render_json(form, include_auth_token=True)
#
#         do_flash(*get_message("PASSWORD_CHANGE"))
#         return redirect(
#             get_url(cv("POST_CHANGE_VIEW")) or get_url(cv("POST_LOGIN_VIEW"))
#         )
#
#     active_password = True if current_user.password else False
#     if _security._want_json(request):
#         form.user = current_user
#         payload = dict(active_password=active_password)
#         return base_render_json(form, additional=payload)
#
#     return _security.render_template(
#         cv("CHANGE_PASSWORD_TEMPLATE"),
#         change_password_form=form,
#         active_password=active_password,
#         **_ctx("change_password"),
#     )
#
