# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for the Stripe Customer → Organisation billing mirror
(spec `finances-02.md` §C). No DB, no app context."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.stripe.customers import (
    CustomerBilling,
    apply_customer_billing_to_org,
    extract_customer_billing,
)


def _org() -> SimpleNamespace:
    return SimpleNamespace(
        billing_email=None,
        billing_vat_number=None,
        billing_address_line1=None,
        billing_address_line2=None,
        billing_postal_code=None,
        billing_city=None,
        billing_country=None,
    )


class TestExtractCustomerBilling:
    def test_dict_payload_full(self):
        customer = {
            "email": "compta@press.example",
            "address": {
                "line1": "1 rue de la Presse",
                "line2": "BP 42",
                "postal_code": "75002",
                "city": "Paris",
                "country": "FR",
            },
            "tax_ids": {"data": [{"value": "FR12345678901", "type": "eu_vat"}]},
        }
        billing = extract_customer_billing(customer)
        assert billing == CustomerBilling(
            email="compta@press.example",
            vat_number="FR12345678901",
            address_line1="1 rue de la Presse",
            address_line2="BP 42",
            postal_code="75002",
            city="Paris",
            country="FR",
        )

    def test_sdk_attribute_access(self):
        customer = SimpleNamespace(
            email="x@y.example",
            address=SimpleNamespace(
                line1="A", line2=None, postal_code="1000", city="Bxl", country="BE"
            ),
            tax_ids=SimpleNamespace(data=[SimpleNamespace(value="BE0123456789")]),
        )
        billing = extract_customer_billing(customer)
        assert billing.email == "x@y.example"
        assert billing.vat_number == "BE0123456789"
        assert billing.city == "Bxl"
        assert billing.country == "BE"

    def test_no_address_no_tax_ids(self):
        billing = extract_customer_billing({"email": "solo@example.com"})
        assert billing.email == "solo@example.com"
        assert billing.vat_number is None
        assert billing.address_line1 is None
        assert billing.country is None

    def test_empty_tax_ids_data(self):
        billing = extract_customer_billing({"tax_ids": {"data": []}})
        assert billing.vat_number is None

    def test_none_customer_is_all_none(self):
        billing = extract_customer_billing(None)
        assert billing == CustomerBilling(None, None, None, None, None, None, None)


class TestApplyCustomerBilling:
    def test_applies_all_present_fields(self):
        org = _org()
        apply_customer_billing_to_org(
            org,
            CustomerBilling(
                email="a@b.example",
                vat_number="FR99",
                address_line1="L1",
                address_line2="L2",
                postal_code="75000",
                city="Paris",
                country="FR",
            ),
        )
        assert org.billing_email == "a@b.example"
        assert org.billing_vat_number == "FR99"
        assert org.billing_country == "FR"

    def test_none_fields_preserve_existing(self):
        """A partial payload (no VAT) must not wipe a previously-synced VAT."""
        org = _org()
        org.billing_vat_number = "FR-EXISTING"
        apply_customer_billing_to_org(
            org,
            CustomerBilling(
                email="new@b.example",
                vat_number=None,
                address_line1=None,
                address_line2=None,
                postal_code=None,
                city=None,
                country=None,
            ),
        )
        assert org.billing_email == "new@b.example"
        assert org.billing_vat_number == "FR-EXISTING"
