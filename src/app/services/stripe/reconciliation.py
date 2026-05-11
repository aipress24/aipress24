# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe subscription reconciliation.

Safety net against missed webhooks: walks every local `Subscription`
that has a `stripe_subscription_id`, fetches the authoritative state
from Stripe, and reports drifts. Does **not** auto-correct — surfaces
the drift so an operator can decide.

Typical use from a nightly cron:

    flask stripe reconcile
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.flask.extensions import db
from app.logging import warn
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    Subscription,
    SubscriptionStatus,
)
from app.modules.wire.models import ArticlePurchase, PurchaseStatus
from app.services.stripe.retriever import retrieve_customer, retrieve_session
from app.services.stripe.utils import load_stripe_api_key

# Stripe subscription statuses considered "active" (subscribed + payable).
_STRIPE_ACTIVE = {"active", "trialing"}

# How far back `reconcile_purchases` looks when sampling rows to verify.
_PURCHASE_LOOKBACK = timedelta(days=30)


@dataclass(frozen=True)
class Drift:
    subscription_id: str  # local Subscription UUID
    stripe_id: str
    issue: str  # "not_found", "status_mismatch", "missing_customer"
    local_status: str = ""
    stripe_status: str = ""

    def as_dict(self) -> dict:
        return {
            "subscription_id": self.subscription_id,
            "stripe_id": self.stripe_id,
            "issue": self.issue,
            "local_status": self.local_status,
            "stripe_status": self.stripe_status,
        }


@dataclass(frozen=True)
class CustomerDrift:
    customer_id: str
    issue: str  # "not_found", "deleted"


@dataclass(frozen=True)
class PurchaseDrift:
    checkout_session_id: str
    issue: str  # "not_found", "payment_status_mismatch"
    local_status: str = ""
    stripe_status: str = ""


def reconcile_subscriptions(session: Session | None = None) -> list[Drift]:
    """Compare every local Subscription's status with Stripe's view.

    Returns a list of drift reports. Empty list means everything is in
    sync.
    """
    if session is None:
        session = db.session

    if not load_stripe_api_key():
        warn("reconcile_subscriptions: STRIPE_SECRET_KEY missing, skipping")
        return []

    drifts: list[Drift] = []
    subs = (
        session.query(Subscription)
        .filter(Subscription.stripe_subscription_id.is_not(None))
        .all()
    )

    for sub in subs:
        stripe_id = sub.stripe_subscription_id or ""
        if not stripe_id:
            continue  # defensive — the filter above should prevent this

        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_id)
        except stripe.InvalidRequestError:
            drifts.append(
                Drift(
                    subscription_id=str(sub.id),
                    stripe_id=stripe_id,
                    issue="not_found",
                )
            )
            continue
        except Exception as exc:
            warn(f"reconcile: unexpected error fetching {stripe_id}: {exc}")
            continue

        local_active = sub.status == SubscriptionStatus.ACTIVE.value
        stripe_status = getattr(stripe_sub, "status", "") or ""
        stripe_active = stripe_status in _STRIPE_ACTIVE

        if local_active != stripe_active:
            drifts.append(
                Drift(
                    subscription_id=str(sub.id),
                    stripe_id=stripe_id,
                    issue="status_mismatch",
                    local_status=sub.status,
                    stripe_status=stripe_status,
                )
            )

    return drifts


def reconcile_customers(session: Session | None = None) -> list[CustomerDrift]:
    """Compare every `Organisation.stripe_customer_id` with Stripe.

    Returns drifts when the Stripe Customer is missing or marked deleted.
    """
    if session is None:
        session = db.session
    if not load_stripe_api_key():
        warn("reconcile_customers: STRIPE_SECRET_KEY missing, skipping")
        return []

    drifts: list[CustomerDrift] = []
    stmt = select(Organisation).where(Organisation.stripe_customer_id.isnot(None))
    for org in session.execute(stmt).scalars():
        customer_id = org.stripe_customer_id or ""
        customer = retrieve_customer(customer_id)
        if customer is None:
            drifts.append(CustomerDrift(customer_id=customer_id, issue="not_found"))
            continue
        if getattr(customer, "deleted", False):
            drifts.append(CustomerDrift(customer_id=customer_id, issue="deleted"))

    return drifts


def reconcile_purchases(session: Session | None = None) -> list[PurchaseDrift]:
    """Sample recent `ArticlePurchase` rows and check their Stripe session.

    Looks at the last 30 days. Surfaces drift when the local payment
    status disagrees with Stripe's view.
    """
    if session is None:
        session = db.session
    if not load_stripe_api_key():
        warn("reconcile_purchases: STRIPE_SECRET_KEY missing, skipping")
        return []

    cutoff = datetime.now(UTC) - _PURCHASE_LOOKBACK
    stmt = (
        select(ArticlePurchase)
        .where(ArticlePurchase.timestamp >= cutoff)
        .where(ArticlePurchase.stripe_checkout_session_id.isnot(None))
    )
    drifts: list[PurchaseDrift] = []
    for purchase in session.execute(stmt).scalars():
        checkout_id = purchase.stripe_checkout_session_id or ""
        stripe_session = retrieve_session(checkout_id)
        if stripe_session is None:
            drifts.append(
                PurchaseDrift(checkout_session_id=checkout_id, issue="not_found"),
            )
            continue
        stripe_paid = stripe_session.payment_status == "paid"
        local_paid = purchase.status == PurchaseStatus.PAID
        if stripe_paid != local_paid:
            drifts.append(
                PurchaseDrift(
                    checkout_session_id=checkout_id,
                    issue="payment_status_mismatch",
                    local_status="paid" if local_paid else "pending",
                    stripe_status=stripe_session.payment_status,
                )
            )

    return drifts
