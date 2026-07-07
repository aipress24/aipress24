# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helper to cancel a Stripe subscription."""

from __future__ import annotations

from typing import TYPE_CHECKING

import stripe

from app.logging import warn
from app.services.stripe.utils import load_stripe_api_key

if TYPE_CHECKING:
    from stripe import Subscription as StripeSubscription


def _get_stripe_subscription(stripe_subscription_id: str) -> StripeSubscription | None:
    """Retrieve a Stripe subscription by id, loading the Stripe API key first.

    Returns ``None`` if Stripe is not configured or the subscription cannot be
    retrieved (logs a warning).
    """
    if not load_stripe_api_key():
        warn(
            f"Cannot retrieve Stripe subscription {stripe_subscription_id!r}: "
            "Stripe API key not found"
        )
        return None
    try:
        return stripe.Subscription.retrieve(stripe_subscription_id)
    except Exception as e:
        warn(f"Failed to retrieve Stripe subscription {stripe_subscription_id!r}: {e}")
        return None


def cancel_stripe_subscription(stripe_subscription_id: str) -> bool:
    """Cancel a Stripe subscription immediately.

    Args:
        stripe_subscription_id: The Stripe subscription identifier.

    Returns:
        True if the subscription was successfully cancelled/deleted or if
        there is nothing to cancel. "False" if Stripe reported an error.
    """
    stripe_sub: StripeSubscription | None = _get_stripe_subscription(
        stripe_subscription_id
    )
    if stripe_sub is None:
        # No Stripe configured or subscription not found
        return True

    try:
        stripe.Subscription.cancel(stripe_subscription_id)
        return True
    except stripe.error.InvalidRequestError as e:
        if "No such subscription" in str(e):
            warn(
                f"Stripe subscription {stripe_subscription_id!r} already removed "
                "or unknown; treating as cancelled"
            )
            return True
        warn(f"Stripe error cancelling subscription {stripe_subscription_id!r}: {e}")
        return False
    except Exception as e:
        warn(f"Failed to cancel Stripe subscription {stripe_subscription_id!r}: {e}")
        return False
