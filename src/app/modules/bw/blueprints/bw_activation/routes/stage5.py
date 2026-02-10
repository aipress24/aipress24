# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 5: External partners management routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.blueprints.bw_activation import bp
from app.modules.bw.blueprints.bw_activation.config import BW_TYPES


@bp.route("/manage-external-partners")
def manage_external_partners():
    """Stage 5: Manage external PR Agencies and Consultants."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation/05_manage_external_partners.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )
