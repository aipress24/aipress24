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
class PrefInterestsPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "interests"
    label = "Centres d'intérêts"
    template = "pages/preferences/interest.j2"
    icon = "clipboard-document-check"

    def context(self) -> dict[str, bool]:
        user = g.user
        profile = user.profile
        return {"hobbies": profile.get_value("hobbies")}

    def post(self):
        if not current_user.is_authenticated:
            raise ValueError("No currently authenticated user")
        if request.form.get("submit") == "cancel":
            return redirect(url_for(f".{self.name}"))

        response = {}
        for key, val in request.form.items():
            response[key] = val
        # search hobbies response
        new_hobbies = response.get("hobbies")
        if not new_hobbies:
            return redirect(url_for(f".{self.name}"))
        user = g.user
        profile = user.profile
        profile.set_value("hobbies", new_hobbies)
        db_session = db.session
        db_session.merge(user)
        db_session.commit()
        return redirect(self.url)
