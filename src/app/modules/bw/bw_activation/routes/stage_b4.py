# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 5: External partners management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import g, redirect, render_template, request, session, url_for

from app.flask.extensions import db

# from werkzeug import Response
# from werkzeug.exceptions import NotFound
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import invite_pr_provider
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    fill_session,
    get_current_press_relation_bw_list,
    get_pending_pr_bw_info_list,
    get_press_relation_bw_list,
)

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


@bp.route("/manage-external-partners", methods=["GET", "POST"])
def manage_external_partners():
    """Stage B4: Manage external PR Agencies and Consultants."""
    # at this stage the BW must be created
    user = cast("User", g.user)
    # Note: current_business_wall() return the BW associated with
    # the current organisation membershop of the user: that means
    # in the future we will need a function permitting to a BW
    # manager EXTERNAL to manage any of its authorized BW
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))
    fill_session(business_wall)
    if user.id not in bw_managers_ids(business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type: str = cast(str, session["bw_type"])
    bw_info: dict[str, Any] = BW_TYPES.get(bw_type, {})

    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    current_pr_bw_list = get_current_press_relation_bw_list(business_wall)
    pending_pr_bw_info = get_pending_pr_bw_info_list(business_wall)
    pr_bw_list = get_press_relation_bw_list()
    pr_bw_list = [bw for bw in pr_bw_list if bw not in current_pr_bw_list]

    if request.method == "POST":
        selected_pr_id = request.form.get("pr_provider")
        warn("Selected PR provider:", selected_pr_id)
        if invite_pr_provider(business_wall, selected_pr_id):
            warn("invite_pr_provider success")
            db.session.commit()
        return redirect(url_for("bw_activation.manage_external_partners"))

    return render_template(
        "bw_activation/B04_manage_external_partners.html",
        bw_type=bw_type,
        bw_info=bw_info,
        pr_bw_list=pr_bw_list,
        current_pr_bw_list=current_pr_bw_list,
        pending_pr_bw_info=pending_pr_bw_info,
    )
