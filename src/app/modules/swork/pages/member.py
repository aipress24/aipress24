# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

from flask import g, make_response, redirect, render_template, request
from sqlalchemy.orm import selectinload

from app.flask.extensions import db, htmx
from app.flask.lib.pages import expose, page
from app.flask.lib.toaster import toast
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.services.social_graph import SocialUser, adapt

from .. import blueprint
from .base import BaseSworkPage
from .members import MembersPage
from .viewmodels import UserVM

TABS = [
    {"id": "profile", "label": "Profil"},
    {"id": "publications", "label": "Publications"},
    {"id": "activities", "label": "Activités"},
    {"id": "groups", "label": "Groupes"},
    {"id": "followees", "label": "Abonnements"},
    {"id": "followers", "label": "Abonnés"},
]


@page
class MemberPage(BaseSworkPage):
    name = "member"
    path = "/members/<id>"
    parent = MembersPage
    template = "pages/member.j2"

    def __init__(self, id: str):
        self.args = {"id": id}
        options = selectinload(User.organisation)
        self.profile = get_obj(id, User, options=options)

    @property
    def label(self) -> str:
        return f"{self.profile.last_name}, {self.profile.first_name}"

    def context(self):
        user_vm = UserVM(self.profile)

        active_tab = request.args.get("tab", "profile")

        followers = user_vm.followers
        if len(followers) > 5:
            followers_sample = random.sample(followers, 5)
        else:
            followers_sample = followers

        return {
            "profile": user_vm,
            "tabs": TABS,
            "active_tab": active_tab,
            "followers_sample": followers_sample,
        }

    def get(self):
        active_tab = request.args.get("tab", "profile")
        if htmx:
            return getattr(self, f"tab_{active_tab}")()
        return super().get()

    def post(self):
        action = request.form["action"]

        match action:
            case "toggle-follow":
                return self.toggle_follow()
            case _:
                return ""

    def toggle_follow(self):
        user: SocialUser = adapt(g.user)
        profile = self.profile
        if user.is_following(profile):
            user.unfollow(profile)
            response = make_response("Suivre")
            toast(response, f"Vous ne suivez plus {profile.full_name}")
        else:
            user.follow(profile)
            response = make_response("Ne plus suivre")
            toast(response, f"Vous suivez a présent {profile.full_name}")

        db.session.commit()

        return response

    @expose
    def tab_profile(self):
        return render_template("pages/member/member--tab-profile.j2", **self.context())

    @expose
    def tab_publications(self):
        return render_template(
            "pages/member/member--tab-publications.j2", **self.context()
        )

    @expose
    def tab_activities(self):
        return render_template(
            "pages/member/member--tab-activities.j2", **self.context()
        )

    @expose
    def tab_groups(self):
        return render_template("pages/member/member--tab-groups.j2", **self.context())

    @expose
    def tab_followers(self):
        return render_template(
            "pages/member/member--tab-followers.j2", **self.context()
        )

    @expose
    def tab_followees(self):
        return render_template(
            "pages/member/member--tab-followees.j2", **self.context()
        )


@blueprint.route("/profile/")
def profile():
    user = g.user
    return redirect(url_for(user))
