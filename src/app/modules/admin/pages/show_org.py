# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask import Response, current_app, request

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.view_model import ViewModel

# from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.organisation import Organisation
from app.services.roles import add_role

from .. import blueprint
from ..invitations import (
    cancel_invitation_users,
    emails_invited_to_organisation,
    invite_users,
)
from ..utils import (
    gc_organisation,
    get_user_per_email,
    remove_user_organisation,
    set_user_organisation,
)
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
                if gc_organisation(self.org):
                    response.headers["HX-Redirect"] = AdminOrgsPage().url
                else:
                    response.headers["HX-Redirect"] = self.url
            case "change_managers_emails":
                self._change_managers_emails()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_leaders_emails":
                self._change_leaders_emails()
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_invitations_emails":
                self._change_invitations_emails()
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
        current_emails = {u.email.lower() for u in org.members}
        # remove users that are not in the new list of members
        for member in org.members:
            if member.email not in new_mails:
                remove_user_organisation(member)
        # add users of the new list that are not in the current list of members
        for mail in new_mails:
            if mail not in current_emails:
                user = get_user_per_email(mail)
                if not user:
                    continue
                set_user_organisation(user, self.org)

    def _change_managers_emails(self) -> None:
        raw_mails = request.form["content"]
        new_mails = set(raw_mails.lower().split())
        org = self.org
        db_session = db.session
        current_managers = [u for u in org.members if u.is_manager]
        current_members_emails = {u.email.lower() for u in org.members}
        current_managers_emails = {u.email.lower() for u in current_managers}
        # remove managers that are not in the new list of managers
        for manager in current_managers:
            if manager.email not in new_mails:
                manager.remove_role(RoleEnum.MANAGER)
                db_session.merge(manager)
                db_session.flush()
        # add users of the new list that are not in the current list of members
        for mail in new_mails:
            if mail not in current_managers_emails:
                if mail not in current_members_emails:
                    continue  # require manager to be already member
                user = get_user_per_email(mail)
                if not user:
                    continue
                add_role(user, RoleEnum.MANAGER)
                db_session.merge(user)
                db_session.flush()
        db_session.commit()

    def _change_leaders_emails(self) -> None:
        raw_mails = request.form["content"]
        new_mails = set(raw_mails.lower().split())
        org = self.org
        db_session = db.session
        current_leaders = [u for u in org.members if u.is_leader]
        current_members_emails = {u.email.lower() for u in org.members}
        current_leaders_emails = {u.email.lower() for u in current_leaders}
        # remove managers that are not in the new list of managers
        for leader in current_leaders:
            if leader.email not in new_mails:
                leader.remove_role(RoleEnum.LEADER)
                db_session.merge(leader)
                db_session.flush()
        # add users of the new list that are not in the current list of members
        for mail in new_mails:
            if mail not in current_leaders_emails:
                if mail not in current_members_emails:
                    continue  # require manager to be already member
                user = get_user_per_email(mail)
                if not user:
                    continue
                add_role(user, RoleEnum.LEADER)
                db_session.merge(user)
                db_session.flush()
        db_session.commit()

    def _change_invitations_emails(self) -> None:
        raw_mails = request.form["content"]
        new_mails = list(set(raw_mails.split()))  # keep mail case
        new_mails_lower = {m.lower() for m in new_mails}
        org = self.org
        current_invitations = emails_invited_to_organisation(org.id)
        canceled = [m for m in current_invitations if m.lower() not in new_mails_lower]
        cancel_invitation_users(canceled, org.id)
        invite_users(new_mails, org.id)

    # def _add_emails(self) -> None:
    #     raw_mails = request.form["content"]
    #     mails = raw_mails.lower().split()
    #     for mail in mails:
    #         user = get_user_per_email(mail)
    #         if not user:
    #             continue
    #         set_user_organisation(user, self.org)


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast(Organisation, self._model)

    def extra_attrs(self):
        members = self.get_members()
        return {
            "members": members,
            "count_members": len(self.org.members),
            "managers": self.org.managers,
            "leaders": self.org.leaders,
            "invitations_emails": emails_invited_to_organisation(self.org.id),
            "logo_url": self.get_logo_url(),
            "screenshot_url": self.get_screenshot_url(),
            "address_formatted": self.org.formatted_address,
        }

    def get_members(self) -> list:
        return list(self.org.members)

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
