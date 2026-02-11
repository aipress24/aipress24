# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 4: Internal roles management routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES


@bp.route("/manage-internal-roles")
def manage_internal_roles():
    """Stage 4: Manage internal Business Wall Managers and PR Managers."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation/04_manage_internal_roles.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )
