# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for the Checkout billing-collection kwargs
(spec `finances-02.md` §C). No DB, no app context."""

from __future__ import annotations

from app.modules.bw.bw_activation.routes.stage3 import _add_billing_collection


class TestAddBillingCollection:
    def test_enables_tax_and_address_collection(self):
        kwargs: dict = {"mode": "subscription"}
        _add_billing_collection(kwargs)
        assert kwargs["tax_id_collection"] == {"enabled": True}
        assert kwargs["billing_address_collection"] == "required"

    def test_customer_update_added_when_reusing_a_customer(self):
        kwargs: dict = {"customer": "cus_123"}
        _add_billing_collection(kwargs)
        assert kwargs["customer_update"] == {"address": "auto", "name": "auto"}

    def test_no_customer_update_for_new_customer_email(self):
        """`customer_update` is invalid without a reused `customer` — Stripe
        would error. A brand-new customer (email branch) must omit it."""
        kwargs: dict = {"customer_email": "new@press.example"}
        _add_billing_collection(kwargs)
        assert "customer_update" not in kwargs
