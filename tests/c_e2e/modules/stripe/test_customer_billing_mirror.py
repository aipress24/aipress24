# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the Stripe Customer → Organisation billing mirror: the
`customer.updated` webhook handler and `flask stripe sync customers`
(spec `finances-02.md` §C)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from app.flask.cli.stripe import sync_customers
from app.models.organisation import Organisation
from app.modules.stripe.views.webhook import on_customer_updated


def _customer_updated_event(customer_id: str):
    payload = {
        "id": customer_id,
        "email": "compta@press.example",
        "address": {
            "line1": "1 rue de la Presse",
            "line2": None,
            "postal_code": "75002",
            "city": "Paris",
            "country": "FR",
        },
        "tax_ids": {"data": [{"value": "FR12345678901", "type": "eu_vat"}]},
    }
    return SimpleNamespace(
        id="evt_cust_upd",
        type="customer.updated",
        data=SimpleNamespace(object=payload),
    )


class TestCustomerUpdatedWebhook:
    def test_mirrors_billing_onto_bound_org(self, fresh_db, app):
        session = fresh_db.session
        org = Organisation(name="Press SA", stripe_customer_id="cus_bound")
        session.add(org)
        session.commit()

        on_customer_updated(_customer_updated_event("cus_bound"))

        session.refresh(org)
        assert org.billing_email == "compta@press.example"
        assert org.billing_vat_number == "FR12345678901"
        assert org.billing_address_line1 == "1 rue de la Presse"
        assert org.billing_postal_code == "75002"
        assert org.billing_city == "Paris"
        assert org.billing_country == "FR"

    def test_unbound_customer_is_a_noop(self, fresh_db, app):
        session = fresh_db.session
        org = Organisation(name="Other", stripe_customer_id="cus_other")
        session.add(org)
        session.commit()

        # Event for a customer no org is bound to → no crash, no change.
        on_customer_updated(_customer_updated_event("cus_unknown"))

        session.refresh(org)
        assert org.billing_email is None


class TestSyncCustomersCLI:
    def test_syncs_billing_from_stripe(self, fresh_db, app):
        session = fresh_db.session
        org = Organisation(name="Press BE", stripe_customer_id="cus_be")
        session.add(org)
        session.commit()

        fake_customer = SimpleNamespace(
            deleted=False,
            email="c@press.be",
            address=SimpleNamespace(
                line1="X", line2=None, postal_code="1000", city="Bxl", country="BE"
            ),
            tax_ids=SimpleNamespace(data=[SimpleNamespace(value="BE0123456789")]),
        )
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=True),
            patch("app.flask.cli.stripe.retrieve_customer", return_value=fake_customer),
        ):
            result = CliRunner().invoke(sync_customers, [])

        assert result.exit_code == 0, result.output
        session.refresh(org)
        assert org.billing_email == "c@press.be"
        assert org.billing_vat_number == "BE0123456789"
        assert org.billing_country == "BE"
        assert "1 organisation(s)" in result.output

    def test_skips_when_no_api_key(self, fresh_db, app):
        with patch("app.flask.cli.stripe.load_stripe_api_key", return_value=False):
            result = CliRunner().invoke(sync_customers, [])
        assert result.exit_code == 0
        assert "skipping" in result.output
