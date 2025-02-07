# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from collections.abc import Callable

# from pprint import pformat
from typing import Any

import stripe
from stripe import Customer, Event, Invoice, Price, Product, Subscription
from stripe.checkout import Session


def warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning: {msg}", file=sys.stderr)


def _stripe_object_retriever(
    klass: type[Customer | Event | Invoice | Price | Product | Session | Subscription],
) -> Callable:
    def retriever(
        item_id: str, **kwargs: Any
    ) -> Customer | Event | Invoice | Price | Product | Session | Subscription | None:
        try:
            return klass.retrieve(item_id, **kwargs)
        except stripe.error.StripeError as e:  # type:ignore
            warning(f"Error retrieving {klass.__name__} for id {item_id}: {e}")  # type:ignore
            return None

    return retriever


retrieve_customer = _stripe_object_retriever(Customer)
retrieve_event = _stripe_object_retriever(Event)
retrieve_invoice = _stripe_object_retriever(Invoice)
retrieve_price = _stripe_object_retriever(Price)
retrieve_product = _stripe_object_retriever(Product)
retrieve_session = _stripe_object_retriever(Session)
retrieve_subscription = _stripe_object_retriever(Subscription)
