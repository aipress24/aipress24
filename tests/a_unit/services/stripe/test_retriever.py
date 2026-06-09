# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.services.stripe.retriever`.

Each `retrieve_*` module-level function delegates to a `StripeClient`
injected via the `client=` keyword-only parameter. Tests construct a
`FakeStripeClient` carrying canned data, pass it in, and assert on
the RETURNED VALUE — no `unittest.mock`, no `monkeypatch`, no
captured-call lists.
"""

from __future__ import annotations

import inspect

from app.services.stripe.retriever import (
    retrieve_customer,
    retrieve_event,
    retrieve_invoice,
    retrieve_price,
    retrieve_product,
    retrieve_session,
    retrieve_subscription,
)

from ._fake_client import FakeStripeClient, stripe_obj


class TestRetrieveCustomer:
    def test_returns_known_customer(self) -> None:
        fake = FakeStripeClient(
            customers={"cus_42": stripe_obj(id="cus_42", email="x@y.z")}
        )
        result = retrieve_customer("cus_42", client=fake)
        assert result is not None
        assert result.id == "cus_42"
        assert result.email == "x@y.z"

    def test_returns_none_when_unknown(self) -> None:
        fake = FakeStripeClient(customers={})
        assert retrieve_customer("cus_missing", client=fake) is None

    def test_returns_none_when_table_empty(self) -> None:
        assert retrieve_customer("cus_any", client=FakeStripeClient()) is None


class TestRetrieveEvent:
    def test_returns_known_event(self) -> None:
        fake = FakeStripeClient(
            events={"evt_1": stripe_obj(id="evt_1", type="checkout.session.completed")}
        )
        result = retrieve_event("evt_1", client=fake)
        assert result is not None
        assert result.type == "checkout.session.completed"

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_event("evt_x", client=FakeStripeClient()) is None


class TestRetrieveInvoice:
    def test_returns_known_invoice(self) -> None:
        fake = FakeStripeClient(
            invoices={"in_1": stripe_obj(id="in_1", amount_due=2_000)}
        )
        result = retrieve_invoice("in_1", client=fake)
        assert result is not None
        assert result.amount_due == 2_000

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_invoice("in_x", client=FakeStripeClient()) is None


class TestRetrievePrice:
    def test_returns_known_price(self) -> None:
        fake = FakeStripeClient(
            prices={"price_1": stripe_obj(id="price_1", unit_amount=500)}
        )
        result = retrieve_price("price_1", client=fake)
        assert result is not None
        assert result.unit_amount == 500

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_price("price_x", client=FakeStripeClient()) is None


class TestRetrieveProduct:
    def test_returns_known_product(self) -> None:
        fake = FakeStripeClient(
            products={"prod_1": stripe_obj(id="prod_1", name="Mon produit")}
        )
        result = retrieve_product("prod_1", client=fake)
        assert result is not None
        assert result.name == "Mon produit"

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_product("prod_x", client=FakeStripeClient()) is None


class TestRetrieveSession:
    def test_returns_known_session(self) -> None:
        fake = FakeStripeClient(
            sessions={"cs_1": stripe_obj(id="cs_1", payment_status="paid")}
        )
        result = retrieve_session("cs_1", client=fake)
        assert result is not None
        assert result.payment_status == "paid"

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_session("cs_x", client=FakeStripeClient()) is None


class TestRetrieveSubscription:
    def test_returns_known_subscription(self) -> None:
        fake = FakeStripeClient(
            subscriptions={"sub_1": stripe_obj(id="sub_1", status="active")}
        )
        result = retrieve_subscription("sub_1", client=fake)
        assert result is not None
        assert result.status == "active"

    def test_returns_none_on_miss(self) -> None:
        assert retrieve_subscription("sub_x", client=FakeStripeClient()) is None


class TestRetrieverContractIsKeywordOnly:
    """Pin that the `client` parameter is keyword-only — callers can't
    accidentally pass it positionally, which would silently shadow a
    real `**kwargs` field the Stripe SDK expects."""

    def test_client_must_be_keyword_only(self) -> None:
        fake = FakeStripeClient(customers={"cus_1": stripe_obj(id="cus_1")})
        # OK : keyword
        assert retrieve_customer("cus_1", client=fake) is not None
        # Not OK : passing the fake positionally would be caught by Python.
        # Verify the signature shape.
        sig = inspect.signature(retrieve_customer)
        client_param = sig.parameters["client"]
        assert client_param.kind == inspect.Parameter.KEYWORD_ONLY
