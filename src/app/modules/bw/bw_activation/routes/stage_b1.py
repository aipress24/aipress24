# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 4: Internal roles management routes."""

from __future__ import annotations

from typing import cast

from flask import g, redirect, render_template, session, url_for

from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import BWRoleType
from app.modules.bw.bw_activation.user_utils import current_business_wall


@bp.route("/manage-organisation-members")
def manage_organisation_membsers():
    """Stage 1: Manage members of Business Wall organisation."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    # Get current business wall and owner information
    user = cast("User", g.user)
    warn("user", user)
    business_wall = current_business_wall(user)
    if not business_wall:
        # should be impossible, it was at least just created
        return ""
    owner_info = None
    warn("BW", business_wall)
    if business_wall.role_assignments:
        warn(business_wall.role_assignments)
        for assignment in business_wall.role_assignments:
            warn(assignment)
            if assignment.role_type == BWRoleType.BW_OWNER.value:
                try:
                    owner_user = get_obj(assignment.user_id, User)
                    owner_info = {
                        "email": owner_user.email,
                        "full_name": owner_user.full_name,
                    }
                except Exception:
                    owner_info = {
                        "email": "N/A",
                        "full_name": "Inconnu",
                    }
                break

    return render_template(
        "bw_activation/B01_manage_organisation_members.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_info=owner_info,
    )
