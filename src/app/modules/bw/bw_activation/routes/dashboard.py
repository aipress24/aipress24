# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dashboard and management hub routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, session, url_for

from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import fill_session

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/dashboard")
def dashboard():
    """Business Wall management dashboard (after activation)."""
    warn("in bw.dashboard")
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw:
        warn("current BW", current_bw)
        fill_session(current_bw)
        if current_bw.owner_id != user.id:
            # not enough right to manage BW (not owner)
            return redirect(url_for("bw_activation.information"))
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation/dashboard.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    return redirect(url_for("bw_activation.index"))
