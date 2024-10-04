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
from app.models.auth import User
from app.modules.kyc.views import admin_info_context

from .. import blueprint
from .base import AdminListPage
from .users import AdminUsersPage

# from typing import Any

# from sqlalchemy.orm import selectinload


@page
class ShowUser(AdminListPage):
    name = "show_member"
    label = "Informations sur l'utilisateur"
    title = "Informations sur l'utilisateur"
    icon = "clipboard-document-check"
    path = "/show_user/<uid>"
    template = "admin/pages/show_user.j2"
    parent = AdminUsersPage

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
        if action == "deactivate":
            self._deactive_profile()
        # no validation
        response = Response("")
        response.headers["HX-Redirect"] = AdminUsersPage().url
        return response

    def _deactive_profile(self) -> None:
        self.user.active = False
        self.user.user_valid_comment = "Utilisateur désactivé"
        self.user.user_date_valid = datetime.now(timezone.utc)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()


@blueprint.route("/show_user/<uid>")
def show_profile(uid: str):
    member = ShowUser(uid)
    return member.render()
