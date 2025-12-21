# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP business wall page."""

from __future__ import annotations

import sys
from typing import Any

from flask import g, render_template, request
from flask_wtf import FlaskForm
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.wip import blueprint

from ._common import get_secondary_menu


@blueprint.route("/org-profile", endpoint="org-profile")
@nav(icon="building-library")
def org_profile():
    """Business Wall"""
    ctx = _build_context()

    return render_template(
        "wip/pages/institutional-page.j2",
        title="Gérer ma page institutionnelle",
        menus={"secondary": get_secondary_menu("org-profile")},
        **ctx,
    )


@blueprint.route("/org-profile", methods=["POST"])
def org_profile_post() -> str | Response:
    """Handle business wall form submission."""
    # Lazy imports to avoid circular import
    from app.modules.admin.org_email_utils import (
        change_invitations_emails,
        change_leaders_emails,
        change_managers_emails,
        change_members_emails,
    )
    from app.modules.wip.forms.business_wall import merge_org_results

    user = g.user
    org = user.organisation if user.is_authenticated else None

    form = request.form
    if "change_bw_data" in form:
        results = form.to_dict(flat=False)
        merge_org_results(org, results)
        db.session.merge(org)
        db.session.commit()
        return _render_business_wall()

    action = request.form.get("action")
    match action:
        case "change_emails":
            raw_mails = request.form["content"]
            change_members_emails(org, raw_mails)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")
        case "change_managers_emails":
            raw_mails = request.form["content"]
            change_managers_emails(org, raw_mails, keep_one=True)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")
        case "change_leaders_emails":
            raw_mails = request.form["content"]
            change_leaders_emails(org, raw_mails)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")
        case "change_invitations_emails":
            raw_mails = request.form["content"]
            change_invitations_emails(org, raw_mails)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")
        case "reload_bw_data":
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")
            return response
        case _:
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org_profile")

    db.session.commit()
    return response


def _render_business_wall() -> str:
    """Render business wall page."""
    ctx = _build_context()
    return render_template(
        "wip/pages/institutional-page.j2",
        title="Gérer ma page institutionnelle",
        menus={"secondary": get_secondary_menu("org-profile")},
        **ctx,
    )


def _build_context() -> dict[str, Any]:
    """Build context for business wall template."""
    # Lazy imports to avoid circular import
    from app.modules.admin.invitations import emails_invited_to_organisation
    from app.modules.kyc.renderer import render_field
    from app.modules.wip.forms.business_wall import BWFormGenerator
    from app.services.stripe.product import stripe_bw_subscription_dict
    from app.services.stripe.utils import load_stripe_api_key

    user = g.user
    org = user.organisation if user.is_authenticated else None

    is_auto = org and org.is_auto
    is_bw_active = org and org.is_bw_active
    is_bw_inactive = org and org.is_bw_inactive
    allow_editing = is_bw_active and user.is_manager
    readonly = not allow_editing

    if is_bw_active:
        load_stripe_api_key()
        _stripe_bw_products = stripe_bw_subscription_dict()
        _current_product = _stripe_bw_products.get(org.stripe_product_id)
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
                org.stripe_product_id,
                file=sys.stderr,
            )
            print("/////   _current_product", _current_product, file=sys.stderr)
            print(
                "/////   current_product_name",
                current_product_name,
                file=sys.stderr,
            )
        form_generator = BWFormGenerator(user=user, readonly=readonly)
        form = form_generator.generate()
    else:
        current_product_name = ""
        form = FlaskForm()

    members = list(org.members) if org else []

    return {
        "org": org,
        "org_name": org.name if org else "",
        "logo_url": _get_logo_url(org),
        "current_product_name": current_product_name,
        "is_auto": is_auto,
        "is_bw_active": is_bw_active,
        "is_bw_inactive": is_bw_inactive,
        "allow_editing": allow_editing,
        "is_manager": user.is_manager,
        "is_leader": user.is_leader,
        "members": members,
        "count_members": len(members),
        "managers": org.managers if org else [],
        "leaders": org.leaders if org else [],
        "invitations_emails": (emails_invited_to_organisation(org.id) if org else []),
        "address_formatted": org.formatted_address if org else "",
        "render_field": render_field,
        "form": form,
    }


def _get_logo_url(org) -> str:
    """Get logo URL for organisation."""
    if not org:
        return "/static/img/transparent-square.png"
    if org.is_auto:
        return "/static/img/logo-page-non-officielle.png"
    return org.logo_image_signed_url()
