# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from typing import Any

from flask import g, request
from flask_wtf import FlaskForm
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)
from app.modules.kyc.renderer import render_field
from app.modules.wip.pages.base import BaseWipPage
from app.modules.wip.pages.home import HomePage
from app.services.stripe.product import stripe_bw_subscription_dict
from app.services.stripe.utils import load_stripe_api_key

from .business_wall_form import BWFormGenerator, merge_org_results

__all__ = ["BusinessWallPage"]


@page
class BusinessWallPage(BaseWipPage):
    name = "org-profile"
    label = "Business Wall"
    title = "Gérer ma page institutionnelle"
    icon = "building-library"

    # path = "/org-page"
    template = "wip/pages/institutional-page.j2"
    parent = HomePage

    form: FlaskForm | None = None
    readonly: bool = False

    def __init__(self) -> None:
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None

    def get_logo_url(self) -> str:
        if not self.org:
            return "/static/img/transparent-square.png"
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        if not self.org.logo_id:
            return "/static/img/transparent-square.png"
        return url_for("api.get_blob", id=self.org.logo_id)

    def context(self) -> dict[str, Any]:
        is_auto = self.org and self.org.is_auto
        is_bw_active = self.org and self.org.is_bw_active
        is_bw_inactive = self.org and self.org.is_bw_inactive
        allow_editing = is_bw_active and self.user.is_manager
        self.readonly = not allow_editing
        if is_bw_active:
            load_stripe_api_key()
            _stripe_bw_products = stripe_bw_subscription_dict()
            _current_product = _stripe_bw_products.get(self.org.stripe_product_id)
            current_product_name = _current_product.name if _current_product else ""
            if not current_product_name:
                print("///// BusinessWallPage.context() BUG", file=sys.stderr)
                print("/////   is_bw_active", is_bw_active, file=sys.stderr)
                print(
                    "/////   _stripe_bw_products keys",
                    list(_stripe_bw_products.keys()),
                    file=sys.stderr,
                )
                print(
                    "/////   org.stripe_product_id",
                    self.org.stripe_product_id,
                    file=sys.stderr,
                )
                print("/////   _current_product", _current_product, file=sys.stderr)
                print(
                    "/////   current_product_name",
                    current_product_name,
                    file=sys.stderr,
                )
            form_generator = BWFormGenerator(user=self.user, readonly=self.readonly)
            self.form = form_generator.generate()
        else:
            current_product_name = ""
            self.form = FlaskForm()
        if self.org:
            members = list(self.org.members)
        else:
            members = []
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "logo_url": self.get_logo_url(),
            "current_product_name": current_product_name,
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
