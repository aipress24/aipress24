# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from typing import Any

from flask import g, make_response, redirect, render_template, request
from sqlalchemy.orm import selectinload

from app.flask.extensions import db, htmx
from app.flask.lib.pages import expose, page
from app.flask.lib.toaster import toast
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.kyc.views import public_info_context
from app.services.social_graph import SocialUser, adapt

from .. import blueprint
from .base import BaseSworkPage
from .masked_fields import MaskFields
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

MASK_FIELDS = {
    "email": "email",
    "mobile": "tel_mobile",
}


@page
class MemberPage(BaseSworkPage):
    name = "member"
    path = "/members/<id>"
    parent = MembersPage
    template = "pages/member.j2"

    def __init__(self, id: str):
        self.args = {"id": id}
        options = selectinload(User.organisation)
        self.user = get_obj(id, User, options=options)

    @property
    def label(self) -> str:
        return f"{self.user.last_name}, {self.user.first_name}"

    def context(self):
        user_vm = UserVM(self.user)

        active_tab = request.args.get("tab", "profile")

        followers = user_vm.followers
        if len(followers) > 5:
            followers_sample = random.sample(followers, 5)
        else:
            followers_sample = followers

        mask_fields: MaskFields = self.filter_email_mobile()
        context = public_info_context(self.user, mask_fields)
        context.update({
            "profile": user_vm,
            "tabs": TABS,
            "active_tab": active_tab,
            "followers_sample": followers_sample,
        })
        return context

    def filter_email_mobile(self) -> MaskFields:
        # def filter_email_mobile(self) -> list[str]:
        """Return list of field names to be masked according to the
        logged user contect type.

        "contact_type" of the logged user can be from PRESSE to ETUDIANT.
        If this method does not find a mode (email) in the permitted list,
        the mode *may* be still allowed as FOLLOWEE contact type, in a later
        stage.
        """
        mask_fields = MaskFields()
        contact_type = g.user.profile.contact_type
        user_allow = self.user.profile.show_contact_details
        for mode, field in MASK_FIELDS.items():
            key = f"{mode}_{contact_type}"
            if not user_allow.get(key):
                mask_fields.add_field(field)
                mask_fields.add_message(f"{mode} not allowed for {contact_type}")
        return self._allow_followee(user_allow, mask_fields)

    def _allow_followee(
        self,
        user_allow: dict[str, Any],
        mask_fields: MaskFields,
    ) -> MaskFields:
        # def _allow_followee(self, mask_fields:list[str]) -> list[str]:
        if not mask_fields.masked:
            # no field masked, no need to check for followee.
            mask_fields.add_message("no field masked")
            return mask_fields
        member_is_follower = None
        for mode in ("email", "mobile"):
            if MASK_FIELDS[mode] not in mask_fields.masked:
                # visibility already allowed
                mask_fields.add_message(f"{mode} already allowed")
                continue
            key_mode = f"{mode}_FOLLOWEE"
            if not user_allow.get(key_mode):
                # followees are not allowed
                mask_fields.add_message(f"{mode}: followees not allowed")
                continue
            if member_is_follower is None:
                # member_is_follower is computed only once :
                # member_is_follower None -> True or False
                member_user: SocialUser = adapt(self.user)
                member_is_follower = member_user.is_following(g.user)
            if not member_is_follower:
                # nothing to do, visibility still not allowed
                mask_fields.add_message(f"{mode}: member is not a follower")
                continue
            # remove mode from mask fields to allow visibility:
            mask_fields.remove_field(MASK_FIELDS[mode])
            mask_fields.add_message(f"{mode}: allowed because followee")
        return mask_fields

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
        logged_user: SocialUser = adapt(g.user)
        if logged_user.is_following(self.user):
            logged_user.unfollow(self.user)
            response = make_response("Suivre")
            toast(response, f"Vous ne suivez plus {self.user.full_name}")
        else:
            logged_user.follow(self.user)
            response = make_response("Ne plus suivre")
            toast(response, f"Vous suivez a présent {self.user.full_name}")

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
    logged_user = g.user
    return redirect(url_for(logged_user))
