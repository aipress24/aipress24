# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe Billing Portal entry point.

Lets a BW Manager (or admin) land on Stripe's hosted customer portal to
manage their subscription: change CB, view invoices, cancel, etc.
Nothing custom — Stripe's own UI does all the work.
"""

from __future__ import annotations

from typing import cast

import stripe
from flask import current_app, flash, g, redirect, url_for

from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import is_bw_manager_or_admin
from app.services.stripe.utils import load_stripe_api_key


@bp.route("/billing-portal", methods=["POST"])
def billing_portal():
    user = cast(User, g.user)
    bw = current_business_wall(user)
    if bw is None or not is_bw_manager_or_admin(user, bw):
        flash("Accès non autorisé.", "error")
        return redirect(url_for("bw_activation.index"))

    sub = bw.subscription
    if sub is None or not sub.stripe_customer_id:
        flash("Aucun abonnement Stripe actif pour ce Business Wall.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        flash("La gestion Stripe n'est pas activée pour votre compte.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    if not load_stripe_api_key():
        warn("billing_portal: missing STRIPE_SECRET_KEY")
        flash("Configuration Stripe manquante.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    portal_session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=url_for("bw_activation.dashboard", _external=True),
    )
    return redirect(portal_session.url, code=303)
