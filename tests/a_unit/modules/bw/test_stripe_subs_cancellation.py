# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`cancel_stripe_subscription` must never claim a cancellation it did not get.

Regression for the audit of 2026-09-02: the helper used to `retrieve`
the subscription first and read *any* failure of that call — a missing
API key, a network error, a refused request — as "nothing to cancel",
returning True. `cancel_business_wall_from_app` then recorded
`stripe_cancelled=True`, closed the BW locally and told the member their
subscription was resilié, while Stripe went on billing them. Silent
success on a money path: nobody files a bug, the charges just continue.
"""

from __future__ import annotations

import stripe

from app.modules.bw.bw_activation.stripe_subs_cancellation import (
    cancel_stripe_subscription,
)


class _RecordingStripeSubscription:
    """Stands in for `stripe.Subscription`, raising what we ask it to.

    A stub rather than a `MagicMock`: a mock answers every attribute
    truthily, which is exactly the failure mode this module had.
    """

    def __init__(self, raises: Exception | None = None) -> None:
        self.raises = raises
        self.cancelled: list[str] = []

    def cancel(self, subscription_id: str):
        if self.raises is not None:
            raise self.raises
        self.cancelled.append(subscription_id)
        return {"id": subscription_id, "status": "canceled"}


def _with_stripe(monkeypatch, app, double, *, api_key="sk_test_dummy"):
    """Point the module at a canned Stripe, for this test only.

    `monkeypatch.setitem` rather than a bare assignment: `app` is
    session-scoped, and a written key stays written for every test that
    follows.
    """
    monkeypatch.setitem(app.config, "STRIPE_SECRET_KEY", api_key)
    monkeypatch.setattr(stripe, "Subscription", double)


def test_a_cancelled_subscription_reports_success(monkeypatch, app) -> None:
    double = _RecordingStripeSubscription()
    with app.test_request_context():
        _with_stripe(monkeypatch, app, double)
        assert cancel_stripe_subscription("sub_live_1") is True
    assert double.cancelled == ["sub_live_1"]


def test_an_unknown_subscription_reports_success(monkeypatch, app) -> None:
    """Stripe not having it is the one failure that means "not running"."""
    error = stripe.InvalidRequestError("No such subscription: sub_gone", param="id")
    double = _RecordingStripeSubscription(raises=error)
    with app.test_request_context():
        _with_stripe(monkeypatch, app, double)
        assert cancel_stripe_subscription("sub_gone") is True


def test_an_unreachable_stripe_reports_failure(monkeypatch, app) -> None:
    """The bug: a transient API error must not read as "cancelled"."""
    double = _RecordingStripeSubscription(raises=stripe.APIConnectionError("boom"))
    with app.test_request_context():
        _with_stripe(monkeypatch, app, double)
        assert cancel_stripe_subscription("sub_live_2") is False
    assert double.cancelled == []


def test_a_refused_request_reports_failure(monkeypatch, app) -> None:
    """An `InvalidRequestError` that is *not* "no such subscription"."""
    error = stripe.InvalidRequestError("Invalid API key provided", param=None)
    double = _RecordingStripeSubscription(raises=error)
    with app.test_request_context():
        _with_stripe(monkeypatch, app, double)
        assert cancel_stripe_subscription("sub_live_3") is False


def test_no_api_key_reports_success_without_calling_stripe(monkeypatch, app) -> None:
    """A deployment without Stripe has no subscription to stop.

    The distinction that matters: an unconfigured key is a static fact
    about the installation, not a call that failed. Refusing here would
    wedge every BW cancellation on a Stripe-less deployment; the failure
    modes worth refusing are the ones above, where Stripe was asked and
    did not answer.
    """
    double = _RecordingStripeSubscription()
    with app.test_request_context():
        _with_stripe(monkeypatch, app, double, api_key=None)
        assert cancel_stripe_subscription("sub_live_4") is True
    assert double.cancelled == []
