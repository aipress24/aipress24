# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B2: Manage organisation members."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, request, session, url_for
from werkzeug import Response

from app.flask.extensions import db
from app.logging import warn
from app.modules.admin.org_email_utils import change_members_emails
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NO_ORGANISATION,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    fill_session,
)

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/manage-organisation-members", methods=["GET", "POST"])
def manage_organisation_members():
    """Stage B2: Manage members of Business Wall organisation."""
    # at this stage the BW must be created
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if not current_bw:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.non_authorized"))
    fill_session(current_bw)
    if user.id not in bw_managers_ids(current_bw):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.non_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    org = current_bw.get_organisation()
    # organisation must be created for the BW (it was created at BW creation if missing)
    if not org:
        session["error"] = ERR_NO_ORGANISATION
        return redirect(url_for("bw_activation.non_authorized"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "change_emails":
            raw_mails = request.form["content"]
            change_members_emails(org, raw_mails, remove_only=True)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(
                "bw_activation.manage_organisation_members"
            )
            db.session.commit()
            return response

    members = list(org.members) if org else []
    warn(members)

    return render_template(
        "bw_activation/B02_manage_organisation_members.html",
        bw_type=bw_type,
        bw_info=bw_info,
        business_wall=current_bw,
        org=org,
        members=members,
    )
