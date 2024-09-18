# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g

from app.flask.lib.pages import page

# from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.kyc.views import admin_info_context

from .. import blueprint
from .base import AdminListPage
from .home import AdminHomePage

# from typing import Any

# from sqlalchemy.orm import selectinload


@page
class ShowUser(AdminListPage):
    name = "member"
    label = "Informations sur l'utilisateur"
    title = "Informations sur l'utilisateur"
    icon = "clipboard-document-check"
    path = "/members/<uid>"

    template = "admin/pages/show_user.j2"
    parent = AdminHomePage

    def __init__(self, uid: str = ""):
        if not uid:  # test
            uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.user = get_obj(id, User, options=options)
        self.user = get_obj(uid, User)

    def context(self):
        context = admin_info_context(self.user)
        context.update(
            {
                "user": self.user,
            }
        )
        return context


@blueprint.route("/profile/<uid>")
def show_profile(uid: str):
    member = ShowUser(uid)
    return member.render()
