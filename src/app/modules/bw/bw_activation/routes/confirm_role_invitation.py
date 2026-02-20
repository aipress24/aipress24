# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Role invitation confirmation route."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, request, session, url_for
from sqlalchemy import select

from app.flask.extensions import db
from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_INVITATION_NOT_FOUND,
    ERR_WRONG_VALIDATION_LINK,
)

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route(
    "/confirm-role-invitation/<bw_id>/<role_type>/<int:user_id>",
    methods=["GET", "POST"],
)
def confirm_role_invitation(bw_id: str, role_type: str, user_id: int):
    """Confirm or reject a role invitation.

    The role assignment status is updated to ACCEPTED or REJECTED
    """
    template = "bw_activation/confirm_role_invitation.html"
    current_user = cast("User", g.user)

    # Security check: user can only access their own invitation
    if current_user.id != user_id:
        warn(f"bad access {current_user.id} to invation for user {user_id}")
        session["error"] = ERR_WRONG_VALIDATION_LINK
        return redirect(url_for("bw_activation.not_authorized"))

    try:
        business_wall = db.session.execute(
            select(BusinessWall).where(BusinessWall.id == bw_id)
        ).scalar_one_or_none()
    except Exception:
        business_wall = None

    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        warn(f"Business wall not found: {bw_id}")
        return redirect(url_for("bw_activation.not_authorized"))

    role_assignment = db.session.execute(
        select(RoleAssignment).where(
            RoleAssignment.business_wall_id == bw_id,
            RoleAssignment.user_id == user_id,
            RoleAssignment.role_type == role_type,
        )
    ).scalar_one_or_none()

    if not role_assignment:
        warn(f"Role assignment not found user {user_id}, BW {bw_id}, role {role_type}")
        session["error"] = ERR_INVITATION_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    # fixme need bw name first
    org = business_wall.get_organisation()
    if org:
        bw_name = org.name
    else:
        bw_name = "(Nom inconnu)"

    bw_role_name = BW_ROLE_TYPE_LABEL.get(role_assignment.role_type, "(rôle inconnu)")

    # Check invitation is pending
    if role_assignment.invitation_status != InvitationStatus.PENDING.value:
        warn(f"Invitation already processed: {role_assignment.invitation_status}")
        return render_template(
            template,
            action=role_assignment.invitation_status,
            already_processed=True,
            role_assignment=role_assignment,
            bw_name=bw_name,
            bw_type=business_wall.bw_type,
            bw_role_name=bw_role_name,
        )

    # Handle form submission (POST)
    if request.method == "POST":
        action = request.form.get("action")

        if action == "accept":
            role_assignment.invitation_status = InvitationStatus.ACCEPTED.value
            role_assignment.accepted_at = datetime.now(UTC)
            warn(f"User {user_id} accepted role {role_type} for BW {bw_name!r}")
        else:
            role_assignment.invitation_status = InvitationStatus.REJECTED.value
            role_assignment.rejected_at = datetime.now(UTC)
            warn(f"User {user_id} rejected role {role_type} for BW {bw_name!r}")

        db.session.flush()

        return render_template(
            template,
            role_assignment=role_assignment,
            action=role_assignment.invitation_status,
            already_processed=False,
            bw_name=bw_name,
            bw_type=business_wall.bw_type,
            bw_role_name=bw_role_name,
        )

    return render_template(
        template,
        role_assignment=role_assignment,
        action="",
        already_processed=False,
        bw_name=bw_name,
        bw_type=business_wall.bw_type,
        bw_role_name=bw_role_name,
    )
