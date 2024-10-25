# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask import Response, current_app, request

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.organisation import Organisation

from .. import blueprint
from ..utils import get_user_per_email, remove_user_organisation, set_user_organisation
from .base import AdminListPage
from .orgs import AdminOrgsPage


@page
class ShowOrg(AdminListPage):
    name = "show_org"
    label = "Informations sur l'organisation"
    title = "Informations sur l'organisation"
    icon = "clipboard-document-check"
    path = "/show_org/<uid>"
    template = "admin/pages/show_org.j2"
    parent = AdminOrgsPage

    def __init__(self, uid: str = ""):
        # if not uid:  # test
        #     uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.org = get_obj(id, User, options=options)
        self.org = get_obj(uid, Organisation)

    def context(self):
        return {"org": OrgVM(self.org)}

    def post(self):
        action = request.form["action"]
        match action:
            case "change_emails":
                self._change_emails()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "add_emails":
                self._add_emails()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = AdminOrgsPage().url
        return response

    def _change_emails(self) -> None:
        raw_mails = request.form["content"]
        new_mails = set(raw_mails.lower().split())
        org = self.org
        current_members = list(
            db.session.query(User).filter(User.organisation_id == org.id).all()
        )
        current_emails = {u.email.lower() for u in current_members}
        # remove users that are not in the new list of members
        for member in current_members:
            if member.email not in new_mails:
                remove_user_organisation(member)
        # add users of the new list that are not in the current list of members
        for mail in new_mails:
            if mail not in current_emails:
                user = get_user_per_email(mail)
                if not user:
                    continue
                set_user_organisation(user, self.org)

    def _add_emails(self) -> None:
        raw_mails = request.form["content"]
        mails = raw_mails.lower().split()
        for mail in mails:
            user = get_user_per_email(mail)
            if not user:
                continue
            set_user_organisation(user, self.org)


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast(Organisation, self._model)

    def extra_attrs(self):
        members = self.get_members()
        return {
            "members": members,
            "count_members": len(members),
            "managers": self.org.managers,
            "leaders": self.org.leaders,
            "logo_url": self.get_logo_url(),
            "screenshot_url": self.get_screenshot_url(),
            "address_formatted": self.org.formatted_address,
        }

    def get_members(self):
        org = self.org
        members = list(
            db.session.query(User).filter(User.organisation_id == org.id).all()
        )
        return members

    def get_logo_url(self):
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        else:
            return self.org.logo_url

    def get_screenshot_url(self):
        if not self.org.screenshot_id:
            return ""
        config = current_app.config
        base_url = config["S3_PUBLIC_URL"]
        url = f"{base_url}/{self.org.screenshot_id}"
        return url
        # return self.org.logo_url


@blueprint.route("/show_org/<uid>")
def show_org_detail(uid: str):
    org_detail = ShowOrg(uid)
    return org_detail.render()
