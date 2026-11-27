# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin page listing active Business Walls without a Stripe subscription."""

from __future__ import annotations

from flask import render_template
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.enums import BWStatus
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Subscription,
    SubscriptionStatus,
)


def _find_active_bws_without_stripe() -> list[BusinessWall]:
    """Return active BWs whose subscription has no `stripe_subscription_id`."""
    stmt = (
        db.select(BusinessWall)
        .join(Subscription, Subscription.business_wall_id == BusinessWall.id)
        .options(joinedload(BusinessWall.subscription))
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
        .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
        .where(
            or_(
                Subscription.stripe_subscription_id.is_(None),
                Subscription.stripe_subscription_id == "",
            )
        )
        .order_by(BusinessWall.created_at.desc())
    )
    return list(db.session.scalars(stmt).unique().all())


@blueprint.route("/bw-no-stripe")
@nav(parent="index", icon="alert-triangle", label="BW no stripe")
def bw_no_stripe():
    """List active Business Walls without an active Stripe subscription."""
    bws = _find_active_bws_without_stripe()
    org_ids = {bw.organisation_id for bw in bws if bw.organisation_id}
    owner_ids = {bw.owner_id for bw in bws if bw.owner_id}

    orgs_by_id = (
        {
            org.id: org
            for org in db.session.scalars(
                db.select(Organisation).where(Organisation.id.in_(org_ids))
            )
        }
        if org_ids
        else {}
    )
    owners_by_id = (
        {
            user.id: user
            for user in db.session.scalars(
                db.select(User).where(User.id.in_(owner_ids))
            )
        }
        if owner_ids
        else {}
    )

    rows = []
    for bw in bws:
        org = orgs_by_id.get(bw.organisation_id) if bw.organisation_id else None
        owner = owners_by_id.get(bw.owner_id) if bw.owner_id else None
        rows.append(
            {
                "bw_id": str(bw.id),
                "bw_name": bw.name or (org.bw_name if org else "") or "—",
                "bw_type": bw.bw_type,
                "org_id": org.id if org else bw.organisation_id,
                "org_name": org.name if org else "—",
                "owner_email": owner.email if owner else "—",
                "created_at": bw.created_at,
            }
        )

    return render_template(
        "admin/pages/bw_no_stripe.j2",
        title="BW no stripe",
        rows=rows,
    )
