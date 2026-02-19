# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B3: Internal roles management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import g, redirect, render_template, request, session, url_for
from werkzeug import Response
from werkzeug.exceptions import NotFound

from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import (
    change_bwmi_emails,
    change_bwpri_emails,
)
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    ERR_UNKNOWN_ACTION,
    bw_managers_ids,
    fill_session,
)

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


@bp.route("/manage-internal-roles", methods=["GET", "POST"])
def manage_internal_roles():
    """Stage B3: Manage internal Business Wall Managers and PR Managers."""
    # at this stage the BW must be created
    user = cast("User", g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.non_authorized"))
    fill_session(business_wall)
    if user.id not in bw_managers_ids(business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.non_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type: str = cast(str, session["bw_type"])
    bw_info: dict[str, Any] = BW_TYPES.get(bw_type, {})

    if request.method == "POST":
        action = request.form.get("action")
        if action == "change_bwmi_invitations":
            raw_mails = request.form["content"]
            change_bwmi_emails(business_wall, raw_mails)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(
                "bw_activation.manage_internal_roles"
            )
            return response
        if action == "change_bwpri_invitations":
            raw_mails = request.form["content"]
            change_bwpri_emails(business_wall, raw_mails)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(
                "bw_activation.manage_internal_roles"
            )
            return response
        session["error"] = ERR_UNKNOWN_ACTION
        warn("unknown action", action)
        return redirect(url_for("bw_activation.non_authorized"))

    # Build context for template
    ctx = _build_context(business_wall, bw_type, bw_info)

    return render_template(
        "bw_activation/B03_manage_internal_roles.html",
        **ctx,
    )


def _build_context(
    business_wall: BusinessWall,
    bw_type: str,
    bw_info: dict[str, str],
) -> dict[str, str | dict | list]:
    """Build context for internal roles template."""
    # Retrieve owner info
    owner_info: dict[str, str] = {}
    if business_wall.role_assignments:
        for assignment in business_wall.role_assignments:
            if assignment.role_type == BWRoleType.BW_OWNER.value:
                try:
                    owner_user = get_obj(assignment.user_id, User)
                    owner_info["email"] = owner_user.email
                    owner_info["full_name"] = owner_user.full_name
                except Exception:
                    owner_info["email"] = "N/A"
                    owner_info["full_name"] = "Inconnu"
                break

    # Initialize lists for BWMi and BWPRi
    bwmi_members: list[User] = []
    bwmi_invitations: list[str] = []
    bwpri_members: list[User] = []
    bwpri_invitations: list[str] = []

    # Process role assignments
    if business_wall.role_assignments:
        for assignment in business_wall.role_assignments:
            role_type = assignment.role_type
            user_id = assignment.user_id
            status = assignment.invitation_status

            # Skip owner (already handled separately)
            if role_type == BWRoleType.BW_OWNER.value:
                continue

            try:
                user = get_obj(user_id, User)
            except NotFound:
                continue

            if role_type == BWRoleType.BWMI.value:
                if status == InvitationStatus.ACCEPTED.value:
                    bwmi_members.append(user)
                else:
                    # For pending/rejected/expired
                    bwmi_invitations.append(user.email)

            elif role_type == BWRoleType.BWPRI.value:
                if status == InvitationStatus.ACCEPTED.value:
                    bwpri_members.append(user)
                else:
                    # For pending/rejected/expired, show as invitation
                    bwpri_invitations.append(user.email)

    return {
        "bw_type": bw_type,
        "bw_info": bw_info,
        "owner_info": owner_info,
        "bwmi_members": bwmi_members,
        "bwmi_invitations": bwmi_invitations,
        "bwpri_members": bwpri_members,
        "bwpri_invitations": bwpri_invitations,
    }
