# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import wtforms as wtf
from flask import g
from flask_wtf import FlaskForm
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.pages import page

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile"
    label = "Profil"
    template = "pages/preferences/profile.j2"
    icon = "user-circle"

    def context(self):
        form = PrefProfileForm(obj=g.user)
        return {
            "form": form,
        }

    def post(self):
        form = PrefProfileForm(obj=g.user)
        # TODO
        # result = form.validate()
        form.populate_obj(g.user)
        db.session.commit()
        return redirect(self.url)


class PrefProfileForm(FlaskForm):
    first_name = wtf.StringField("Prénom")
    last_name = wtf.StringField("Nom")

    organisation_name = wtf.StringField("Organisation")
    job_title = wtf.StringField("Fonction")
    job_description = wtf.TextAreaField("Fonction détaillée")

    bio = wtf.TextAreaField("Bio")
    education = wtf.TextAreaField("Cursus")
    hobbies = wtf.TextAreaField("Intérêts / hobbies")
