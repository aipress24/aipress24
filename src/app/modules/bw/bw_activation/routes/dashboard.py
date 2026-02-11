# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dashboard and management hub routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES


@bp.route("/dashboard")
def dashboard():
    """Business Wall management dashboard (after activation)."""
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
