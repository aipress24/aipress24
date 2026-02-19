# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 6: Missions/permissions assignment routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.utils import init_missions_state


@bp.route("/assign-missions")
def assign_missions():
    """Stage 6: Assign permissions/missions to PR Managers."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    # Initialize missions state in session if not present
    init_missions_state()

    return render_template(
        "bw_activation/B05_assign_missions.html",
        bw_type=bw_type,
        bw_info=bw_info,
        missions=session["missions"],
    )
