# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 3: Activation routes (free and paid)."""

from __future__ import annotations

from flask import redirect, render_template, request, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES

# ===== FREE ACTIVATION =====


@bp.route("/activate-free/<bw_type>")
def activate_free_page(bw_type):
    """Step 3: Page for free BW activation with CGV acceptance."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation/activate_free.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/activate_free/<bw_type>", methods=["POST"])
def activate_free(bw_type):
    """Process free Business Wall activation."""
    if bw_type not in BW_TYPES or not BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    cgv_accepted = request.form.get("cgv_accepted") == "on"
    if cgv_accepted:
        session["bw_type"] = bw_type
        session["bw_activated"] = True
        return redirect(url_for("bw_activation.confirmation_free"))

    return redirect(url_for("bw_activation.activate_free_page", bw_type=bw_type))


@bp.route("/confirmation/free")
def confirmation_free():
    """Confirmation page for free BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation/02_activation_gratuit_confirme.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


# ===== PAID ACTIVATION =====


@bp.route("/pricing/<bw_type>")
def pricing_page(bw_type):
    """Step 3: Page for paid BW pricing information."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    if not session.get("contacts_confirmed"):
        return redirect(url_for("bw_activation.nominate_contacts"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation/pricing.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )


@bp.route("/set_pricing/<bw_type>", methods=["POST"])
def set_pricing(bw_type):
    """Set pricing information for paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    # Validate CGV acceptance (required for paid types)
    cgv_accepted = request.form.get("cgv_accepted") == "on"
    if not cgv_accepted:
        # CGV not accepted, redirect back to pricing page
        return redirect(url_for("bw_activation.pricing_page", bw_type=bw_type))

    pricing_field = str(BW_TYPES[bw_type]["pricing_field"])
    try:
        pricing_value = int(request.form.get(pricing_field, "0"))
        if pricing_value > 0:
            session["bw_type"] = bw_type
            session["pricing_value"] = pricing_value
            session["cgv_accepted"] = True  # Store CGV acceptance
            return redirect(url_for("bw_activation.payment", bw_type=bw_type))
    except ValueError:
        pass

    return redirect(url_for("bw_activation.index"))


@bp.route("/payment/<bw_type>")
def payment(bw_type):
    """Payment page for paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    if not session.get("pricing_value"):
        return redirect(url_for("bw_activation.index"))

    bw_info = BW_TYPES[bw_type]
    return render_template(
        "bw_activation/payment.html",
        bw_type=bw_type,
        bw_info=bw_info,
        pricing_value=session["pricing_value"],
    )


@bp.route("/simulate_payment/<bw_type>", methods=["POST"])
def simulate_payment(bw_type):
    """Simulate payment and activate paid BW."""
    if bw_type not in BW_TYPES or BW_TYPES[bw_type]["free"]:
        return redirect(url_for("bw_activation.index"))

    if session.get("pricing_value"):
        session["bw_activated"] = True
        return redirect(url_for("bw_activation.confirmation_paid"))

    return redirect(url_for("bw_activation.index"))


@bp.route("/confirmation/paid")
def confirmation_paid():
    """Confirmation page for paid BW activation."""
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    return render_template(
        "bw_activation/03_activation_payant_confirme.html",
        bw_type=bw_type,
        bw_info=bw_info,
    )
