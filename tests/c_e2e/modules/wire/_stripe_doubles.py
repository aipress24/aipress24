# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe objects, reduced to the fields the code actually reads.

`MagicMock` answers *anything*, truthily: a test that puts one at the
Stripe boundary validates correct code and code reading a non-existent
attribute equally well. `notes/lessons-learned.md` tells that story about
a guard on `item.publisher.review_required`, which silently took the
wrong branch.

These doubles carry only the fields production reads. Any other
attribute raises `AttributeError`, which is exactly the signal we want:
if production starts reading something else, the test says so.

They remain doubles. The real Stripe boundary is covered by
`app/services/stripe/reconciliation.py` and by the `stripe_price`
mirror, fed by the webhooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckoutSession:
    """What `stripe.checkout.Session.create` returns.

    The views read only `url`, which they redirect to with a 303.
    """

    url: str = "https://stripe.test/checkout/session"


@dataclass(frozen=True)
class Price:
    """What `stripe.Price.retrieve` returns.

    Only `recurring` is read, by `buy`, to choose between `subscription`
    and `payment` mode. `None` means "one-off".

    *Displayed* amounts no longer come through here: they come from the
    `stripe_price` mirror. This double therefore only serves the buy POST.
    """

    recurring: dict[str, Any] | None = None


@dataclass(frozen=True)
class EventData:
    """A webhook event's `data`. `object` carries the name Stripe gives
    it, even though that shadows the builtin."""

    object: dict[str, Any]


@dataclass(frozen=True)
class Event:
    """A webhook event, as the router reads it: `id`, `type` and
    `data.object`. Nothing else is consulted."""

    id: str
    type: str
    data: EventData


def checkout_completed(
    *,
    session_id: str,
    purchase_id: int,
    product_type: str,
    amount_total: int = 1500,
    extra_metadata: dict[str, str] | None = None,
) -> Event:
    """A paid `checkout.session.completed`, ready for the router."""
    metadata = {"purchase_id": str(purchase_id), "product_type": product_type}
    metadata.update(extra_metadata or {})
    return Event(
        id=f"evt_{session_id}",
        type="checkout.session.completed",
        data=EventData(
            object={
                "id": session_id,
                "mode": "payment",
                "metadata": metadata,
                "payment_intent": f"pi_{session_id}",
                "amount_total": amount_total,
                "currency": "eur",
                "payment_status": "paid",
            }
        ),
    )
