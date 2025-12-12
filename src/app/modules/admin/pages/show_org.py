# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask import Response, current_app, request
from svcs.flask import container

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)
from app.modules.admin.utils import (
    delete_full_organisation,
    gc_organisation,
    merge_organisation,
    toggle_org_active,
)
from app.modules.kyc.renderer import render_field
from app.modules.wip.pages.business_wall.business_wall_form import (
    BWFormGenerator,
    merge_org_results,
)
from app.services.sessions import SessionService

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

    def __init__(self, uid: str = "") -> None:
        # if not uid:  # test
        #     uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.org = get_obj(id, User, options=options)
        self.org = get_obj(uid, Organisation)
        self.ro_session_key = f"readonly_form_bw_{self.org.id}"

    def context(self):
        session_service = container.get(SessionService)
        readonly = session_service.get(self.ro_session_key)
        if readonly == "RW":
            readonly_flag = False
        else:
            readonly_flag = True
        form_generator = BWFormGenerator(org=self.org, readonly=readonly_flag)
        self.form = form_generator.generate()
        return {
            "org": OrgVM(self.org),
            "render_field": render_field,
            "readonly_form_bw": readonly_flag,
            "form": self.form,
        }

    def apply_bw_modification(self) -> None:
        form = request.form
        results = form.to_dict(flat=False)
        merge_org_results(self.org, results)
        merge_organisation(self.org)

    def post(self):  # noqa: PLR0915
        action = request.form["action"]
        match action:
            case "allow_modify_bw":
                session_service = container.get(SessionService)
                session_service.set(self.ro_session_key, "RW")
                response = Response("")
                response.headers["HX-Redirect"] = (
                    f"{self.url}?reload=1#bw-form-container"
                )
                return response
            case "cancel_modification_bw":
                session_service = container.get(SessionService)
                session_service.set(self.ro_session_key, "RO")
                response = Response("")
                response.headers["HX-Redirect"] = (
                    f"{self.url}?reload=2#bw-form-container"
                )
                return response
            case "validate_modification_bw":
                self.apply_bw_modification()
                session_service = container.get(SessionService)
                session_service.set(self.ro_session_key, "RO")
                response = Response("")
                response.headers["HX-Redirect"] = (
                    f"{self.url}?reload=3#bw-form-container"
                )
                return response
            case "toggle_org_active":
                toggle_org_active(self.org)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "delete_org":
                change_invitations_emails(self.org, "")
                delete_full_organisation(self.org)
                response = Response("")
                response.headers["HX-Redirect"] = AdminOrgsPage().url
            case "change_emails":
                raw_mails = request.form["content"]
                change_members_emails(self.org, raw_mails)
                response = Response("")
                if gc_organisation(self.org):
                    response.headers["HX-Redirect"] = AdminOrgsPage().url
                else:
                    response.headers["HX-Redirect"] = self.url
            case "change_managers_emails":
                raw_mails = request.form["content"]
                change_managers_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_leaders_emails":
                raw_mails = request.form["content"]
                change_leaders_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_invitations_emails":
                raw_mails = request.form["content"]
                change_invitations_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = AdminOrgsPage().url
        # Commit all changes at request boundary
        db.session.commit()
        return response


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast("Organisation", self._model)

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
        return self.org.logo_image_signed_url()

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
