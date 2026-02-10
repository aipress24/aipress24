# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 7: Content configuration routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.blueprints.bw_activation_full import bp
from app.modules.bw.blueprints.bw_activation_full.config import BW_TYPES


@bp.route("/configure-content")
def configure_content():
    """Stage 7: Configure Business Wall content."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation_full.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation_full/07_configure_content.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )
