from __future__ import annotations

from typing import Any

from flask import g, request
from flask_wtf import FlaskForm
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)
from app.modules.kyc.renderer import render_field

from .base import BaseWipPage
from .business_wall_form import BWFormGenerator, merge_org_results
from .home import HomePage

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


__all__ = ["BusinessWallPage"]


@page
class BusinessWallPage(BaseWipPage):
    name = "org-profile"
    label = "Business Wall"
    title = "Gérer ma page institutionnelle"  # type: ignore
    icon = "building-library"

    # path = "/org-page"
    template = "wip/pages/institutional-page.j2"
    parent = HomePage

    def __init__(self):
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        self.form = None
        self.readonly: bool = False

    def context(self) -> dict[str, Any]:
        is_auto = self.org and self.org.is_auto
        is_bw_active = self.org and self.org.is_bw_active
        is_bw_inactive = self.org and self.org.is_bw_inactive
        allow_editing = is_bw_active and self.user.is_manager
        self.readonly = not allow_editing
        self.bwform = BWFormGenerator(self.user, self.org, self.readonly)
        self.form = self.bwform.generate() if is_bw_active else FlaskForm()
        if self.org:
            members = list(self.org.members)
        else:
            members = []
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": self.org.bw_type if self.org else "",
            "is_auto": is_auto,
            "is_bw_active": is_bw_active,
            "is_bw_inactive": is_bw_inactive,
            "allow_editing": allow_editing,
            "is_manager": self.user.is_manager,
            "is_leader": self.user.is_leader,
            "members": members,
            "count_members": len(members),
            "managers": self.org.managers if self.org else [],
            "leaders": self.org.leaders if self.org else [],
            "invitations_emails": (
                emails_invited_to_organisation(self.org.id) if self.org else []
            ),
            "address_formatted": self.org.formatted_address if self.org else "",
            "render_field": render_field,
            "form": self.form,
        }

    def post(self) -> str | Response:
        """Non hx post.

        Used for submitting a form requiring in-page WTFom validation.
        """
        form = request.form
        if "change_bw_data" in form:
            results = form.to_dict(flat=False)
            self.merge_form(results)
            return self.render()

        action = request.form.get("action")
        match action:
            case "change_emails":
                raw_mails = request.form["content"]
                change_members_emails(self.org, raw_mails)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case "change_managers_emails":
                raw_mails = request.form["content"]
                change_managers_emails(self.org, raw_mails, keep_one=True)
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
            # case "change_bw_data":
            #     results = request.form.to_dict(flat=False)
            #     self.merge_form(results)
            #     response = Response("")
            #     response.headers["HX-Redirect"] = self.url
            #     return response
            case "reload_bw_data":
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = self.url
        return response

    def merge_form(self, results: dict[str, Any]) -> None:
        """Load the results dictionnary into self.org."""
        merge_org_results(self.org, results)
        db_session = db.session
        db_session.merge(self.org)
        db_session.commit()
