# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for the Stripe Price display helper.

DB-touching tests for ``stripe_price_display`` and ``upsert_price_from_event``
live at the b_integration tier (see tests/b_integration/services/stripe/
test_prices.py). What stays here is the short-circuit branch that never
reaches ``db.session`` — passing a falsy ``price_id`` returns the
fallback string straight away.
"""

from __future__ import annotations

from app.services.stripe.prices import stripe_price_display


class TestStripePriceDisplay:
    """`stripe_price_display(price_id)` short-circuits on falsy input."""

    def test_empty_price_id_returns_fallback(self) -> None:
        assert stripe_price_display("") == "—"
        assert stripe_price_display(None) == "—"
