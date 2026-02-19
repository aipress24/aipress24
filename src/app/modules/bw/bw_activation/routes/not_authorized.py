# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Not-authorized/error page route."""

from __future__ import annotations

from flask import render_template, session

from app.modules.bw.bw_activation import bp


@bp.route("/not-authorized")
def not_authorized():
    """Display error page for not authorized access or other errors."""
    error_message = session.get("error") or "Accès non autorisé."
    session.pop("error", None)

    return render_template(
        "bw_activation/not_authorized.html",
        error_message=error_message,
    )
