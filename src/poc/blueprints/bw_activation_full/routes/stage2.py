# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 2: Contact nomination routes."""

from __future__ import annotations

from flask import redirect, render_template, request, session, url_for

from poc.blueprints.bw_activation_full import bp
from poc.blueprints.bw_activation_full.config import BW_TYPES
from poc.blueprints.bw_activation_full.utils import get_mock_owner_data


@bp.route("/nominate-contacts")
def nominate_contacts():
    """Step 2: Nominate Business Wall Owner and Paying Party."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

    bw_type = session.get("bw_type")
    bw_info = BW_TYPES.get(bw_type, {})

    # Pre-fill with mock user data (in real app, use current_user)
    owner_data = get_mock_owner_data()

    return render_template(
        "bw_activation_full/02_nominate_contacts.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_data=owner_data,
    )


@bp.route("/submit-contacts", methods=["POST"])
def submit_contacts():
    """Process contacts nomination and redirect to activation."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation_full.confirm_subscription"))

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
        return redirect(
            url_for("bw_activation_full.activate_free_page", bw_type=bw_type)
        )
    return redirect(url_for("bw_activation_full.pricing_page", bw_type=bw_type))
