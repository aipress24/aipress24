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
from app.services.stripe._client import StripeClient, default_client
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


# ── Pure decision helpers ───────────────────────────────────────────
#
# Each helper takes plain data (no DB session, no Stripe client) and
# returns the drift the orchestrator should record — or None for
# "everything matches". This lets the rule itself be unit-tested at
# microsecond speed without a DB fixture, while the orchestration
# functions below stay thin and call out to these for every row they
# walk.


def detect_subscription_drift(
    *,
    local_id: str,
    local_status: str,
    stripe_id: str,
    stripe_sub: object | None,
) -> Drift | None:
    """Compare a single local Subscription to its Stripe counterpart.

    Returns a `Drift` to record, or `None` if the row is aligned.

    `stripe_sub` is whatever `client.retrieve_subscription` returned —
    a Stripe SDK object (`.status` attribute) or `None` if the id is
    unknown upstream.
    """
    if stripe_sub is None:
        return Drift(
            subscription_id=local_id,
            stripe_id=stripe_id,
            issue="not_found",
        )

    local_active = local_status == SubscriptionStatus.ACTIVE.value
    stripe_status = getattr(stripe_sub, "status", "") or ""
    stripe_active = stripe_status in _STRIPE_ACTIVE

    if local_active != stripe_active:
        return Drift(
            subscription_id=local_id,
            stripe_id=stripe_id,
            issue="status_mismatch",
            local_status=local_status,
            stripe_status=stripe_status,
        )
    return None


def detect_customer_drift(
    *,
    customer_id: str,
    stripe_customer: object | None,
) -> CustomerDrift | None:
    """Compare a single local Organisation's customer ref to Stripe.

    `not_found` vs `deleted` are intentionally distinct issue codes :
    `not_found` means « we have an id Stripe never heard of » (worth
    investigating), `deleted` means « Stripe killed this customer
    upstream » (clean up locally).
    """
    if stripe_customer is None:
        return CustomerDrift(customer_id=customer_id, issue="not_found")
    if getattr(stripe_customer, "deleted", False):
        return CustomerDrift(customer_id=customer_id, issue="deleted")
    return None


def detect_purchase_drift(
    *,
    checkout_session_id: str,
    local_status: object,
    stripe_session: object | None,
) -> PurchaseDrift | None:
    """Compare a single local ArticlePurchase to its Stripe Checkout
    Session. `local_status` is the SQLAlchemy enum value (typically a
    `PurchaseStatus` member or its `.value`) — we read it via equality
    so this helper isn't coupled to the enum class.
    """
    if stripe_session is None:
        return PurchaseDrift(
            checkout_session_id=checkout_session_id,
            issue="not_found",
        )

    stripe_paid = getattr(stripe_session, "payment_status", "") == "paid"
    local_paid = local_status == PurchaseStatus.PAID
    if stripe_paid != local_paid:
        return PurchaseDrift(
            checkout_session_id=checkout_session_id,
            issue="payment_status_mismatch",
            local_status="paid" if local_paid else "pending",
            stripe_status=getattr(stripe_session, "payment_status", ""),
        )
    return None


def reconcile_subscriptions(
    session: Session | None = None,
    *,
    client: StripeClient | None = None,
) -> list[Drift]:
    """Compare every local Subscription's status with Stripe's view.

    Returns a list of drift reports. Empty list means everything is in
    sync.
    """
    if session is None:
        session = db.session

    if client is None:
        if not load_stripe_api_key():
            warn("reconcile_subscriptions: STRIPE_SECRET_KEY missing, skipping")
            return []
        client = default_client()

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
        stripe_sub = client.retrieve_subscription(stripe_id)
        drift = detect_subscription_drift(
            local_id=str(sub.id),
            local_status=sub.status,
            stripe_id=stripe_id,
            stripe_sub=stripe_sub,
        )
        if drift is not None:
            drifts.append(drift)

    return drifts


def reconcile_customers(
    session: Session | None = None,
    *,
    client: StripeClient | None = None,
) -> list[CustomerDrift]:
    """Compare every `Organisation.stripe_customer_id` with Stripe.

    Returns drifts when the Stripe Customer is missing or marked deleted.
    """
    if session is None:
        session = db.session
    if client is None:
        if not load_stripe_api_key():
            warn("reconcile_customers: STRIPE_SECRET_KEY missing, skipping")
            return []
        client = default_client()

    drifts: list[CustomerDrift] = []
    stmt = select(Organisation).where(Organisation.stripe_customer_id.isnot(None))
    for org in session.execute(stmt).scalars():
        customer_id = org.stripe_customer_id or ""
        customer = client.retrieve_customer(customer_id)
        drift = detect_customer_drift(
            customer_id=customer_id, stripe_customer=customer
        )
        if drift is not None:
            drifts.append(drift)

    return drifts


def reconcile_purchases(
    session: Session | None = None,
    *,
    client: StripeClient | None = None,
) -> list[PurchaseDrift]:
    """Sample recent `ArticlePurchase` rows and check their Stripe session.

    Looks at the last 30 days. Surfaces drift when the local payment
    status disagrees with Stripe's view.
    """
    if session is None:
        session = db.session
    if client is None:
        if not load_stripe_api_key():
            warn("reconcile_purchases: STRIPE_SECRET_KEY missing, skipping")
            return []
        client = default_client()

    cutoff = datetime.now(UTC) - _PURCHASE_LOOKBACK
    stmt = (
        select(ArticlePurchase)
        .where(ArticlePurchase.timestamp >= cutoff)
        .where(ArticlePurchase.stripe_checkout_session_id.isnot(None))
    )
    drifts: list[PurchaseDrift] = []
    for purchase in session.execute(stmt).scalars():
        checkout_id = purchase.stripe_checkout_session_id or ""
        stripe_session = client.retrieve_session(checkout_id)
        drift = detect_purchase_drift(
            checkout_session_id=checkout_id,
            local_status=purchase.status,
            stripe_session=stripe_session,
        )
        if drift is not None:
            drifts.append(drift)

    return drifts
