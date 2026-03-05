# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 6: Missions/permissions assignment routes."""

from __future__ import annotations

from typing import Any, cast

from flask import redirect, render_template, request, session, url_for

# from app.flask.extensions import db
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    fill_session,
    init_missions_state,
)


@bp.route("/assign-missions", methods=["GET", "POST"])
def assign_missions():
    """Stage B6: Assign permissions/missions to PR Managers."""
    # at this stage the BW must be created
    user = cast(User, g.user)

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

    # Initialize missions state in session if not present
    init_missions_state()

    if request.method == "POST":
        # Update missions from form data
        missions = session["missions"]
        missions["press_release"] = bool(request.form.get("mission_press_release"))
        missions["events"] = bool(request.form.get("mission_events"))
        missions["missions"] = bool(request.form.get("mission_missions"))
        missions["projects"] = bool(request.form.get("mission_projects"))
        missions["internships"] = bool(request.form.get("mission_internships"))
        missions["apprenticeships"] = bool(request.form.get("mission_apprenticeships"))
        missions["doctoral"] = bool(request.form.get("mission_doctoral"))
        session["missions"] = missions

        warn(missions)

        # Determine redirect based on button clicked
        action = request.form.get("action", "finish")
        warn(action)

        if action == "previous":
            if bw_type == "pr":
                previous = "bw_activation.manage_internal_roles"
            else:
                previous = "bw_activation.manage_external_partners"
            return redirect(url_for(previous))
        if action == "finish":
            return redirect(url_for("bw_activation.dashboard"))
        msg = f"Unknown action {action!r}"
        warn(msg)
        raise ValueError(msg)

    return render_template(
        "bw_activation/B06_assign_missions.html",
        bw_type=bw_type,
        bw_info=bw_info,
        missions=session["missions"],
    )
