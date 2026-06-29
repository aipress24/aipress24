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
from stripe import InvalidRequestError

from app.flask.extensions import db
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

    customer_id = _resolve_stripe_customer_id(bw)
    if not customer_id:
        flash("Aucun abonnement Stripe actif pour ce Business Wall.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        flash("La gestion Stripe n'est pas activée pour votre compte.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    if not load_stripe_api_key():
        warn("billing_portal: missing STRIPE_SECRET_KEY")
        flash("Configuration Stripe manquante.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=url_for("bw_activation.dashboard", _external=True),
        )
    except InvalidRequestError as exc:
        err_msg = str(exc)
        if "No such customer" in err_msg:
            warn(
                f"billing_portal: stored Stripe customer {customer_id} not found; "
                "clearing stale reference."
            )
            _clear_stripe_customer_id(bw)
            flash(
                "Votre identifiant de client Stripe n'a pas été trouvé. La référence locale a été "
                "réinitialisée. Si vous avez un abonnement payant, contactez le support.",
                "error",
            )
            return redirect(url_for("bw_activation.dashboard"))
        raise

    return redirect(portal_session.url, code=303)


def _resolve_stripe_customer_id(bw) -> str | None:
    """Read the Stripe customer id from the Organisation, with a Subscription
    fallback for rows that pre-date the `Organisation.stripe_customer_id`
    migration. Cf. `specs/finances.md` §3.
    """
    org = bw.get_organisation()
    if org is not None and org.stripe_customer_id:
        return org.stripe_customer_id
    sub = bw.subscription
    if sub is not None and sub.stripe_customer_id:
        return sub.stripe_customer_id
    return None


def _clear_stripe_customer_id(bw) -> None:
    """Clear stale Stripe customer ids stored on the Organisation and/or
    the BW Subscription so that the next checkout can create a new
    customer id.
    """
    org = bw.get_organisation()
    if org is not None and org.stripe_customer_id:
        org.stripe_customer_id = None
    sub = bw.subscription
    if sub is not None and sub.stripe_customer_id:
        sub.stripe_customer_id = None
    db.session.commit()
