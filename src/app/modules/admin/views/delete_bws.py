# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to delete all Business Walls."""

from __future__ import annotations

import stripe
from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import update

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.logging import warn
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.subscription import Subscription
from app.services.stripe.utils import load_stripe_api_key


def _cancel_stripe_subscriptions() -> int:
    """Cancel all active Stripe subscriptions linked to local BusinessWalls.

    Returns the number of successfully cancelled subscriptions.
    """
    if not load_stripe_api_key():
        warn("Stripe API key not configured; skipping Stripe subscription cancellation")
        return 0

    cancelled = 0
    subscriptions = db.session.scalars(
        db.select(Subscription).where(Subscription.stripe_subscription_id.is_not(None))
    ).all()

    for sub in subscriptions:
        stripe_sub_id = sub.stripe_subscription_id
        if not stripe_sub_id:
            continue
        try:
            stripe.Subscription.delete(stripe_sub_id)
            cancelled += 1
        except Exception as e:
            warn(
                f"Failed to cancel Stripe subscription {stripe_sub_id!r} "
                f"for BW {sub.business_wall_id}: {e}"
            )

    return cancelled


def _remove_all_bw() -> int:
    """Remove all Business Walls and clear related user/org fields.

    Mirrors the logic in scripts/remove_all_bw.py, with the addition of
    cancelling linked Stripe subscriptions first.

    Returns the number of BusinessWall records deleted.
    """
    bw_count = db.session.query(BusinessWall).count()
    if bw_count == 0:
        return 0

    # 1. Cancel linked Stripe subscriptions (best-effort, never blocks local cleanup)
    _cancel_stripe_subscriptions()

    # 2. Clear selected_bw_id for all users
    db.session.execute(update(User).values(selected_bw_id=None))

    # 3. Clear BW-related fields on all organisations
    db.session.execute(
        update(Organisation).values(
            bw_id=None,
            bw_active=None,
            bw_name="",
        )
    )

    # 4. Delete all BusinessWall records (cascade handles associated data)
    db.session.query(BusinessWall).delete()

    db.session.commit()
    return bw_count


@blueprint.route("/delete-bws", methods=["GET", "POST"])
@nav(parent="index", icon="trash-2", label="Delete BWs")
def delete_bws():
    """Confirmation page for deletion."""
    bw_count = db.session.query(BusinessWall).count()

    if request.method == "POST":
        deleted = _remove_all_bw()
        if deleted:
            flash(
                f"{deleted} Business Wall(s) and associated data have been deleted.",
                "success",
            )
        else:
            flash("No Business Wall records found. Nothing to delete.", "info")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin/pages/delete_bws.j2",
        title="Delete Business Walls",
        bw_count=bw_count,
    )
