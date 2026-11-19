# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall activation helpers shared between Stripe webhooks and checkout."""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger

from app.enums import BWStatus
from app.flask.extensions import db
from app.logging import warn
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_creation import ensure_bw_owner_role
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)


def activate_bw_from_checkout(
    *,
    bw: BusinessWall,
    customer_id: str,
    subscription_id: str,
    checkout_session_id: str,
) -> None:
    """Wire a Stripe Checkout success into the local BW / Subscription.

    Caller is responsible for committing. Kept side-effect-free at the DB
    transaction level so tests can call this helper directly inside their
    transaction wrapper without leaking state into the next test.
    """
    sub = bw.subscription
    if sub is None:
        sub = Subscription(
            business_wall_id=bw.id,
            pricing_field="stripe",
            pricing_tier="via_pricing_table",
            monthly_price=0,
            annual_price=0,
        )
        db.session.add(sub)

    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = subscription_id
    sub.stripe_checkout_session_id = checkout_session_id
    sub.status = SubscriptionStatus.ACTIVE.value
    sub.started_at = datetime.now(UTC)

    _bind_customer_to_organisation(bw, customer_id)

    # Link organisation to BW
    if bw.organisation_id:
        org = db.session.get(Organisation, bw.organisation_id)
        if org:
            active_bw = get_active_business_wall_for_organisation(org)
            if active_bw is not None and active_bw.id != bw.id:
                # fix bug #0370, do not create duplicate BW
                warn(
                    f"Checkout activation: organisation {org.id} already has active BW "
                    f"{active_bw.id}, refusing to overwrite with duplicate BW {bw.id}"
                )
                return
            org.bw_id = bw.id
            org.bw_active = bw.bw_type
            # Sync the BW display name.
            org.bw_name = bw.name or org.bw_name or org.name or ""

    bw.status = BWStatus.ACTIVE.value
    ensure_bw_owner_role(bw)
    logger.info(
        f"BW {bw.id} activated via Stripe Checkout "
        f"(customer={customer_id}, subscription={subscription_id})"
    )


def _bind_customer_to_organisation(bw: BusinessWall, customer_id: str) -> None:
    """Pin the Stripe customer to the BW's organisation, first time only.

    A previous binding is never overwritten — silent reassignment would
    detach the org from its existing Stripe history.
    """
    if not (bw.organisation_id and customer_id):
        return
    org = db.session.get(Organisation, bw.organisation_id)
    if org is None or org.stripe_customer_id:
        return
    org.stripe_customer_id = customer_id
