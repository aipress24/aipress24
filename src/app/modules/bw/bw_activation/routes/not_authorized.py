# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Not-authorized/error page route."""

from __future__ import annotations

from flask import render_template, session

from app.modules.bw.bw_activation import bp


@bp.route("/not-authorized")
def not_authorized():
    """Display error page for not authorized access or other errors.

    Ticket 0271 : a refusal the user can act on may carry an action
    (label + URL) alongside the message — « votre organisation n'est pas
    renseignée » is a dead end without a link to go and renseign it. All
    three keys are one-shot, popped on read like the message itself.
    """
    error_message = session.pop("error", None) or "Accès non autorisé."
    error_action_url = session.pop("error_action_url", None)
    error_action_label = session.pop("error_action_label", None)

    return render_template(
        "bw_activation/not_authorized.html",
        error_message=error_message,
        # A URL without a label would render an unclickable-looking button.
        error_action_url=error_action_url if error_action_label else None,
        error_action_label=error_action_label,
    )
