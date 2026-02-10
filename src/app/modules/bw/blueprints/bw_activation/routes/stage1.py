# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 1: Subscription confirmation routes."""

from __future__ import annotations

from flask import redirect, render_template, session, url_for

from app.modules.bw.blueprints.bw_activation import bp
from app.modules.bw.blueprints.bw_activation.config import BW_TYPES
from app.modules.bw.blueprints.bw_activation.utils import init_session


@bp.route("/")
def index():
    """Redirect to confirmation subscription page."""
    init_session()
    return redirect(url_for("bw_activation.confirm_subscription"))


@bp.route("/confirm-subscription")
def confirm_subscription():
    """Step 1: Confirm or change subscription type."""
    init_session()
    suggested_type = session.get("suggested_bw_type", "media")
    return render_template(
        "bw_activation/00_confirm_subscription.html",
        bw_types=BW_TYPES,
        suggested_bw_type=suggested_type,
    )


@bp.route("/select-subscription/<bw_type>", methods=["POST"])
def select_subscription(bw_type):
    """Confirm or select a subscription type and redirect to contacts nomination."""
    if bw_type not in BW_TYPES:
        return redirect(url_for("bw_activation.confirm_subscription"))

    session["bw_type"] = bw_type
    session["bw_type_confirmed"] = True

    # After subscription selection, go to contacts nomination
    return redirect(url_for("bw_activation.nominate_contacts"))


@bp.route("/activation-choice")
def activation_choice():
    """Step 2: Business Wall activation page (all types - for visual validation)."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    return render_template(
        "bw_activation/01_activation_choice.html",
        bw_types=BW_TYPES,
    )
