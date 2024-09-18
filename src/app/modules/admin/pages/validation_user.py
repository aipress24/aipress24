# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime, timezone

from flask import Response, g, request

from app.flask.extensions import db
from app.flask.lib.pages import page

# from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User, merge_values_from_other_user
from app.modules.kyc.views import admin_info_context

from .. import blueprint
from .base import AdminListPage
from .new_users import AdminNewUsersPage


@page
class ValidationUser(AdminListPage):
    name = "member"
    label = "Validation de l'inscription"
    title = "Validation de l'inscription"
    icon = "clipboard-document-check"
    path = "/validation_profile/<uid>"
    template = "admin/pages/validation_user.j2"
    parent = AdminNewUsersPage

    def __init__(self, uid: str = ""):
        if not uid:  # test
            uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.user = get_obj(id, User, options=options)
        self.user = get_obj(uid, User)

    def context(self):
        context = admin_info_context(self.user)
        context.update({
            "user": self.user,
        })
        return context

    def post(self):
        action = request.form["action"]
        import sys

        print("/////////", "POST", action, file=sys.stderr)

        if action == "validate":
            self._validate_profile()
        # no validation
        response = Response("")
        response.headers["HX-Redirect"] = AdminNewUsersPage().url
        return response

    def _validate_profile(self) -> None:
        # either a clone (modification) or plain user (creation)
        if self.user.email_backup:
            self._validate_profile_modified()
        else:
            self._validate_profile_created()

    def _validate_profile_modified(self) -> None:
        # user is a clone of orig user
        orig_user = get_obj(self.user.cloned_user_id, User)
        merge_values_from_other_user(orig_user, self.user)
        orig_user.user_valid_comment = "Modifications validées"
        orig_user.active = True
        orig_user.user_date_valid = datetime.now(timezone.utc)
        db_session = db.session
        db_session.merge(orig_user)
        db_session.delete(self.user)
        # db_session.add(user)
        db_session.commit()

    def _validate_profile_created(self) -> None:
        # user is a plain new User
        self.user.active = True
        self.user.user_valid_comment = "Nouvel utilisateur validé"
        self.user.user_date_valid = datetime.now(timezone.utc)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()


@blueprint.route("/validation_profile/<uid>")
def validation_profile(uid: str):
    member = ValidationUser(uid)
    return member.render()
