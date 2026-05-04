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
from typing import TYPE_CHECKING

import stripe
from sqlalchemy.orm import Session

from app.flask.extensions import db
from app.logging import warn
from app.modules.bw.bw_activation.models import (
    Subscription,
    SubscriptionStatus,
)
from app.services.stripe.utils import load_stripe_api_key

if TYPE_CHECKING:
    pass


# Stripe subscription statuses considered "active" (subscribed + payable).
_STRIPE_ACTIVE = {"active", "trialing"}


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
