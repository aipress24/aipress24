# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall Activation blueprint.

This blueprint demonstrates the Business Wall activation workflow:
- Free activation for Media organizations (accept CGV)
- Paid activation for PR organizations (enter client count, simulate payment)
- Role assignment after activation
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

bp = Blueprint("bw_activation", __name__, template_folder="../templates")


def init_session():
    """Initialize session with default values if not set."""
    if "org_type" not in session:
        session["org_type"] = None  # "MEDIA" or "PR"
    if "bw_activated" not in session:
        session["bw_activated"] = False
    if "role" not in session:
        session["role"] = None
    if "client_count" not in session:
        session["client_count"] = None


@bp.route("/")
def index():
    """Main page - Business Wall activation workflow."""
    init_session()
    return render_template(
        "bw_activation.html",
        org_type=session.get("org_type"),
        bw_activated=session.get("bw_activated"),
        role=session.get("role"),
        client_count=session.get("client_count"),
    )


@bp.route("/set_org_type", methods=["POST"])
def set_org_type():
    """Set organization type (MEDIA or PR)."""
    org_type = request.form.get("org_type")
    if org_type in ["MEDIA", "PR"]:
        session["org_type"] = org_type
        session["bw_activated"] = False
        session["role"] = None
        session["client_count"] = None
    return redirect(url_for("bw_activation.index"))


@bp.route("/activate_free", methods=["POST"])
def activate_free():
    """Activate Business Wall for free (Media path)."""
    if session.get("org_type") == "MEDIA":
        cgv_accepted = request.form.get("cgv_accepted") == "on"
        if cgv_accepted:
            session["bw_activated"] = True
            session["role"] = "Owner"
    return redirect(url_for("bw_activation.index"))


@bp.route("/set_client_count", methods=["POST"])
def set_client_count():
    """Set client count for PR organizations."""
    if session.get("org_type") == "PR":
        try:
            client_count = int(request.form.get("client_count", 0))
            if client_count > 0:
                session["client_count"] = client_count
        except ValueError:
            pass
    return redirect(url_for("bw_activation.index"))


@bp.route("/simulate_payment", methods=["POST"])
def simulate_payment():
    """Simulate payment and activate Business Wall (PR path)."""
    if session.get("org_type") == "PR" and session.get("client_count"):
        session["bw_activated"] = True
        session["role"] = "Owner"
    return redirect(url_for("bw_activation.index"))


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    return redirect(url_for("bw_activation.index"))
