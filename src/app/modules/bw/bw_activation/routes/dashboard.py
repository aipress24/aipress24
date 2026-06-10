# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dashboard and management hub routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, session, url_for

from app.flask.extensions import db
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import InvitationStatus
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    get_manageable_business_walls_for_user,
)
from app.modules.bw.bw_activation.utils import (
    ERR_NOT_MANAGER,
    fill_session,
    is_bw_manager_or_admin,
)

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.bw.bw_activation.models import BusinessWall


def _bw_user_role_label(user: User, current_bw: BusinessWall | None) -> str:
    if not current_bw:
        return ""
    if current_bw.owner_id == user.id:
        return BW_ROLE_TYPE_LABEL["BW_OWNER"]
    user_role_label = ""
    if current_bw.role_assignments:
        for assignment in current_bw.role_assignments:
            if (
                assignment.user_id == user.id
                and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            ):
                user_role_label = BW_ROLE_TYPE_LABEL.get(
                    assignment.role_type, assignment.role_type
                )
                break
    return user_role_label


@bp.route("/dashboard")
def dashboard():
    """Business Wall management dashboard (after activation)."""
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw:
        if current_bw.status in (BWStatus.CANCELLED.value, BWStatus.DRAFT.value):
            return redirect(url_for("bw_activation.index"))
        fill_session(current_bw)
        if not is_bw_manager_or_admin(user, current_bw):
            # not enough right to manage BW (not owner and not admin)
            session["error"] = ERR_NOT_MANAGER
            return redirect(url_for("bw_activation.not_authorized"))
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    manageable_bws = get_manageable_business_walls_for_user(user)
    active_manageable = [
        bw for bw in manageable_bws if bw.status == BWStatus.ACTIVE.value
    ]

    user_role_label = _bw_user_role_label(user, current_bw)

    return render_template(
        "bw_activation/dashboard.html",
        bw_type=bw_type,
        bw_info=bw_info,
        current_bw=current_bw,
        active_manageable=active_manageable,
        user_role_label=user_role_label,
    )


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    user = cast("User", g.user)
    if user and not user.is_anonymous:
        user.selected_bw_id = None
        db.session.commit()
    return redirect(url_for("bw_activation.index"))
