# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 2: Contact nomination routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import redirect, render_template, request, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import StdDict, get_current_user_data

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/nominate-contacts")
def nominate_contacts():
    """Step 2: Nominate Business Wall Owner and Paying Party."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    bw_type = session.get("bw_type")
    bw_info = BW_TYPES.get(bw_type, {})

    owner_data: StdDict = get_current_user_data()

    return render_template(
        "bw_activation/02_nominate_contacts.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_data=owner_data,
    )


@bp.route("/submit-contacts", methods=["POST"])
def submit_contacts():
    """Process contacts nomination and redirect to activation."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    # Store contact information in session
    session["owner_first_name"] = request.form.get("owner_first_name")
    session["owner_last_name"] = request.form.get("owner_last_name")
    session["owner_email"] = request.form.get("owner_email")
    session["owner_phone"] = request.form.get("owner_phone")

    same_as_owner = request.form.get("same_as_owner") == "on"
    if same_as_owner:
        session["payer_first_name"] = session["owner_first_name"]
        session["payer_last_name"] = session["owner_last_name"]
        session["payer_email"] = session["owner_email"]
        session["payer_phone"] = session["owner_phone"]
    else:
        session["payer_first_name"] = request.form.get("payer_first_name")
        session["payer_last_name"] = request.form.get("payer_last_name")
        session["payer_email"] = request.form.get("payer_email")
        session["payer_phone"] = request.form.get("payer_phone")

    session["contacts_confirmed"] = True

    # Redirect to appropriate activation page based on BW type
    bw_type = session.get("bw_type")
    if BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.activate_free_page", bw_type=bw_type))
    return redirect(url_for("bw_activation.pricing_page", bw_type=bw_type))
