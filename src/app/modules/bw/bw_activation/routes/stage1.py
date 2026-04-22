# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 1: Subscription confirmation routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import current_app, g, redirect, render_template, session, url_for
from werkzeug.wrappers import Response

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    get_business_wall_for_user,
    get_manageable_business_walls_for_user,
    guess_best_bw_type,
)
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    fill_session,
    init_session,
)

if TYPE_CHECKING:
    from app.models.auth import User


def _check_valid_organisation(user: User) -> Response | None:
    """Check that user has a valid (non-deleted) organisation.

    Returns:
        Redirect response if organisation is invalid, None if valid.
    """
    org = user.organisation
    if not org or org.deleted_at is not None:
        session["error"] = (
            "Vous devez appartenir à une organisation valide pour activer un Business Wall."
        )
        return redirect(url_for("bw_activation.not_authorized"))
    return None


@bp.route("/")
def index():
    """Entry point for BW dashboard / activation flow."""
    user = cast("User", g.user)
    init_session()

    # Check user has a valid (non-deleted) organisation
    if error_response := _check_valid_organisation(user):
        return error_response

    # Check all BWs the user can manage (owner, BWMi, BWMe, BWPRe, etc.)
    manageable_bws = get_manageable_business_walls_for_user(user)
    active_manageable = [
        bw for bw in manageable_bws if bw.status != BWStatus.CANCELLED.value
    ]

    if not active_manageable:
        # No manageable BW — check if org has an active BW but user lacks rights
        org_bw = get_business_wall_for_user(user)
        if org_bw and org_bw.status != BWStatus.CANCELLED.value:
            session["error"] = ERR_NOT_MANAGER
            return redirect(url_for("bw_activation.not_authorized"))
        else:
            # No BW at all — start activation flow
            session["suggested_bw_type"] = guess_best_bw_type(user).value
            return redirect(url_for("bw_activation.confirm_subscription"))

    if len(active_manageable) == 1:
        # Only one BW, direct access
        bw = active_manageable[0]
        fill_session(bw)
        return redirect(url_for("bw_activation.dashboard"))
    # several BW: select BW page
    return redirect(url_for("bw_activation.select_bw"))


@bp.route("/confirm-subscription")
def confirm_subscription():
    """Step 1: Confirm or change subscription type."""
    user = cast("User", g.user)
    init_session()

    # Check user has a valid (non-deleted) organisation
    if error_response := _check_valid_organisation(user):
        return error_response

    suggested_type = session.get("suggested_bw_type", "media")
    return render_template(
        "bw_activation/00_confirm_subscription.html",
        bw_types=BW_TYPES,
        suggested_bw_type=suggested_type,
    )


@bp.route("/select-subscription/<bw_type>", methods=["POST"])
def select_subscription(bw_type: str):
    """Confirm or select a subscription type and redirect to contacts nomination."""
    user = cast("User", g.user)

    # Check user has a valid (non-deleted) organisation
    if error_response := _check_valid_organisation(user):
        return error_response

    if bw_type not in BW_TYPES:
        return redirect(url_for("bw_activation.confirm_subscription"))

    session["bw_type"] = bw_type
    session["bw_type_confirmed"] = True

    # After subscription selection, go to contacts nomination
    return redirect(url_for("bw_activation.nominate_contacts"))


@bp.route("/activation-choice")
def activation_choice():
    """Step 2: Business Wall activation page (all types - for visual validation)."""
    user = cast("User", g.user)

    # Check user has a valid (non-deleted) organisation
    if error_response := _check_valid_organisation(user):
        return error_response

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    return render_template(
        "bw_activation/01_activation_choice.html",
        bw_types=BW_TYPES,
        stripe_live_enabled=current_app.config.get("STRIPE_LIVE_ENABLED", False),
    )


@bp.route("/information")
def information():
    """Display basic information about the current Business Wall."""
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if not current_bw:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    bw_type_info = BW_TYPES.get(current_bw.bw_type, {})
    return render_template(
        "bw_activation/information.html",
        business_wall=current_bw,
        bw_type_info=bw_type_info,
    )
