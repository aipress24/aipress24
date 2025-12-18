# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g, request, url_for
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db

from .base import BasePreferencesPage
from .home import PrefHomePage


# @page  # Disabled - using views instead
class PrefInterestsPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "interests"
    label = "Centres d'intérêts"
    template = "pages/preferences/interests.j2"
    icon = "clipboard-document-check"

    def context(self) -> dict[str, str]:
        user = g.user
        profile = user.profile
        return {"hobbies": profile.get_value("hobbies")}

    def post(self):
        if not current_user.is_authenticated:
            msg = "No currently authenticated user"
            raise ValueError(msg)

        if request.form.get("submit") == "cancel":
            return redirect(url_for(f".{self.name}"))

        hobbies = request.form.get("hobbies", "")
        user = g.user
        profile = user.profile
        profile.set_value("hobbies", hobbies)
        db.session.merge(user)
        db.session.commit()
        return redirect(self.url)
