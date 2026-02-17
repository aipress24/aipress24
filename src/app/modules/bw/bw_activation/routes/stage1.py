# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 1: Subscription confirmation routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    guess_best_bw_type,
)
from app.modules.bw.bw_activation.utils import fill_session, init_session

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/")
def index():
    """Redirect to confirmation subscription page."""
    user = cast("User", g.user)
    init_session()
    current_bw = current_business_wall(user)
    if current_bw:
        if current_bw.owner_id == user.id:
            fill_session(current_bw)
            return redirect(url_for("bw_activation.dashboard"))
        # not enough right to manage BW (not owner)
        return redirect(url_for("bw_activation.information"))
    session["suggested_bw_type"] = guess_best_bw_type(user).value
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
