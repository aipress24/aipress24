# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g, request, url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.pages import page

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefContactOptionsPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "contact-options"
    label = "Options de contact"
    template = "pages/preferences/pref-contact.j2"
    icon = "at-symbol"

    def context(self) -> dict[str, bool]:
        user = g.user
        profile = user.profile
        return {"show": profile.all_contact_details()}

    def post(self):
        if not current_user.is_authenticated:
            msg = "No currently authenticated user"
            raise ValueError(msg)
        if request.form.get("submit") == "cancel":
            return redirect(url_for(f".{self.name}"))

        response = {}
        for key, val in request.form.items():
            response[key] = val
        user = g.user
        profile = user.profile
        profile.parse_form_contact_details(response)
        db_session = db.session
        db_session.merge(user)
        db_session.commit()
        return redirect(self.url)
