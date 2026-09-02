# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helper to cancel a Stripe subscription."""

from __future__ import annotations

import stripe

from app.logging import warn
from app.services.stripe.utils import load_stripe_api_key

#: Stripe's own wording when the subscription id is unknown to it. Kept
#: as a fallback: `InvalidRequestError` also fires for a malformed id or
#: a wrong-mode key, and only the message distinguishes them.
_UNKNOWN_SUBSCRIPTION = "No such subscription"


def cancel_stripe_subscription(stripe_subscription_id: str) -> bool:
    """Cancel a Stripe subscription immediately.

    Args:
        stripe_subscription_id: The Stripe subscription identifier.

    Returns:
        True when Stripe has cancelled the subscription, when it reports
        no such subscription, or when this deployment has no Stripe at
        all. **False whenever we asked Stripe and did not get an
        answer** — a network failure, a refused call.

    A `retrieve` used to run first and *any* failure of it was read as
    "nothing to cancel", so a transient outage had the caller record a
    successful cancellation while Stripe kept billing. The pre-flight
    is gone: the `cancel` call below already reports an unknown
    subscription, and that is the only failure that means the
    subscription is not running.

    An unconfigured API key stays a `True`, deliberately. It is a static
    fact about the deployment, not a call that failed — there is no
    Stripe here to bill anyone, and refusing would wedge every
    cancellation on an installation that never used Stripe.
    """
    if not load_stripe_api_key():
        warn(
            f"Not cancelling Stripe subscription {stripe_subscription_id!r}: "
            "no Stripe API key configured on this deployment"
        )
        return True

    try:
        stripe.Subscription.cancel(stripe_subscription_id)
    except stripe.InvalidRequestError as e:
        if _UNKNOWN_SUBSCRIPTION in str(e):
            warn(
                f"Stripe subscription {stripe_subscription_id!r} already removed "
                "or unknown; treating as cancelled"
            )
            return True
        warn(f"Stripe error cancelling subscription {stripe_subscription_id!r}: {e}")
        return False
    except stripe.StripeError as e:
        warn(f"Failed to cancel Stripe subscription {stripe_subscription_id!r}: {e}")
        return False
    return True
