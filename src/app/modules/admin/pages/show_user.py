# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from flask import Response, g, request

from app.constants import LABEL_COMPTE_DESACTIVE, LOCAL_TZ
from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.pages import page

# from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.kyc.views import admin_info_context
from app.services.roles import add_role

from .. import blueprint
from ..utils import gc_organisation, remove_user_organisation
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

    def __init__(self, uid: str = "") -> None:
        if not uid:  # test
            uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.user = get_obj(id, User, options=options)
        self.user = get_obj(uid, User)

    def context(self):
        context = admin_info_context(self.user)
        context.update({"user": self.user, "org": self.user.organisation})
        return context

    def post(self):
        action = request.form["action"]
        match action:
            case "deactivate":
                self._deactive_profile()
                response = Response("")
                response.headers["HX-Redirect"] = AdminUsersPage().url
            case "remove_org":
                self._remove_organisation()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "toggle-manager":
                self._toggle_manager()
                response = Response("")
            case "toggle-leader":
                self._toggle_leader()
                response = Response("")
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = AdminUsersPage().url
        return response

    def _deactive_profile(self) -> None:
        self.user.active = False
        self.user.validation_status = LABEL_COMPTE_DESACTIVE
        self.user.validated_at = now(LOCAL_TZ)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()

    def _remove_organisation(self) -> None:
        previous_organisation = self.user.organisation
        remove_user_organisation(self.user)
        gc_organisation(previous_organisation)

    def _toggle_manager(self) -> None:
        if not self.user.organisation or self.user.organisation.is_auto:
            # not allowed for AUTO organisations.
            # This method call should never happen.
            return
        if self.user.is_manager:
            self.user.remove_role(RoleEnum.MANAGER)
        else:
            add_role(self.user, RoleEnum.MANAGER)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()

    def _toggle_leader(self) -> None:
        if not self.user.organisation or self.user.organisation.is_auto:
            # not allowed for AUTO organisations.
            # This method call should never happen.
            return
        if self.user.is_leader:
            self.user.remove_role(RoleEnum.LEADER)
        else:
            add_role(self.user, RoleEnum.LEADER)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()


@blueprint.route("/show_user/<uid>")
def show_profile(uid: str):
    member = ShowUser(uid)
    return member.render()
