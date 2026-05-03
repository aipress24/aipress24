# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stripe webhook event dispatch coverage.

Drives `stripe/views/webhook.py:on_received_event` for every
`event.type` listed in `_EVENT_HANDLER_NAMES` plus an unmanaged
type. The handlers themselves are exercised :

- `subscription_schedule.*` (7 types) — handler bodies are
  `pass`-only ; covering these proves the dispatch routing
  (`_EVENT_HANDLER_NAMES` lookup + `globals()[handler_name]`)
  works for each registered event type.
- `unmanaged_event` — fired with an arbitrary type
  (`invoice.payment_succeeded`) ; covers the fallback branch.
- `checkout.session.completed` with `mode=subscription` and
  missing/invalid `bw_id` — covers the early-return warnings
  in `on_checkout_session_completed` (UUID parse fail, BW
  lookup miss).

`customer.subscription.*` (8 types) require a real
`retrieve_customer` Stripe API call ; not covered here. They
need a Customer-object monkey-patch (future Sprint).

Drives end-to-end :
- `stripe.views.webhook.webhooks` (POST /webhook handler).
- `stripe.views.webhook.on_received_event` (dispatch).
- `stripe.views.webhook._EVENT_HANDLER_NAMES` (full table).
- 7 `on_subscription_schedule_*` handlers.
- `on_checkout_session_completed` early-return branches.
- `unmanaged_event` (fallback).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from playwright.sync_api import Page

# All `subscription_schedule.*` types — handlers are pass-only.
# Firing each proves the dispatch lookup works.
_SCHEDULE_EVENT_TYPES: list[str] = [
    "subscription_schedule.aborted",
    "subscription_schedule.canceled",
    "subscription_schedule.completed",
    "subscription_schedule.created",
    "subscription_schedule.expiring",
    "subscription_schedule.released",
    "subscription_schedule.updated",
]


@pytest.mark.parametrize("event_type", _SCHEDULE_EVENT_TYPES)
def test_webhook_subscription_schedule_event_returns_200(
    page: Page, base_url: str, event_type: str
) -> None:
    """All `subscription_schedule.*` events dispatch to their pass
    handler and the webhook returns 200.

    Uses the synthetic-mode `fire-webhook` helper with a fake
    `bw_id` (the schedule handlers don't read the object, so any
    payload works)."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": event_type,
            "mode": "subscription",
            "bw_id": str(uuid4()),
            "customer_email": f"test+{uuid4().hex[:8]}@example.com",
        },
    )
    assert fire_resp.status == 200, (
        f"fire-webhook ({event_type}) HTTP {fire_resp.status} : "
        f"{fire_resp.text()[:300]}"
    )
    data = fire_resp.json()
    assert data["fired"] is True
    assert data["event_type"] == event_type
    assert data["webhook_status"] == 200, (
        f"webhook handler returned {data['webhook_status']} for "
        f"event_type={event_type} : {data.get('webhook_body')!r}"
    )


# All `customer.subscription.*` types — handlers call
# `_make_customer_subscription_info` (which itself calls
# `retrieve_customer`, `retrieve_product`, `retrieve_invoice`).
# These retrievers are mocked at extension load time
# (`_patched_customer_retrieve` etc), so any synthetic
# Subscription-shaped event drives the handler's full body.
_CUSTOMER_SUB_EVENT_TYPES: list[str] = [
    "customer.subscription.created",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.pending_update_applied",
    "customer.subscription.pending_update_expired",
    "customer.subscription.resumed",
    "customer.subscription.trial_will_end",
    "customer.subscription.updated",
]


@pytest.mark.parametrize("event_type", _CUSTOMER_SUB_EVENT_TYPES)
def test_webhook_customer_subscription_event_returns_200(
    page: Page, base_url: str, event_type: str
) -> None:
    """All `customer.subscription.*` events drive their handler
    end-to-end (`_make_customer_subscription_info` →
    `_check_subscription_product` → mocked `retrieve_*` calls →
    `_register_bw_subscription` warning branch since the synthetic
    customer email doesn't match a real user).

    Webhook returns 200. Coverage gain : ~120 stmts in
    `stripe/views/webhook.py` previously uncovered."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": event_type,
            # Customer ID is propagated to the synthetic
            # `retrieve_customer` mock (returns email
            # `<id>@mock-stripe.invalid`). Since no user with that
            # email exists, `_register_bw_subscription` logs the
            # « no user found » warning and returns — covering
            # that branch too.
        },
    )
    assert fire_resp.status == 200, (
        f"fire-webhook ({event_type}) HTTP {fire_resp.status} : "
        f"{fire_resp.text()[:300]}"
    )
    data = fire_resp.json()
    assert data["fired"] is True
    assert data["event_type"] == event_type
    assert data["webhook_status"] == 200, (
        f"webhook handler returned {data['webhook_status']} for "
        f"event_type={event_type} : {data.get('webhook_body')!r}"
    )


def test_webhook_unmanaged_event_type_returns_200(
    page: Page, base_url: str
) -> None:
    """An event type not in `_EVENT_HANDLER_NAMES` falls through to
    `unmanaged_event` and the webhook returns 200.

    Covers the dispatcher's fallback branch
    (`on_received_event` else clause)."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": "invoice.payment_succeeded",
            "mode": "payment",
            "bw_id": str(uuid4()),
        },
    )
    assert fire_resp.status == 200
    data = fire_resp.json()
    assert data["webhook_status"] == 200, data.get("webhook_body")


def test_webhook_checkout_subscription_unknown_bw_id_returns_200(
    page: Page, base_url: str
) -> None:
    """`checkout.session.completed` with `mode=subscription` and a
    `bw_id` that doesn't exist in the DB hits the
    `« checkout.session.completed for unknown BW »` warning branch
    in `on_checkout_session_completed`. Webhook still returns 200
    (idempotent / safe by design)."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": "checkout.session.completed",
            "mode": "subscription",
            # Random UUID — will pass UUID() parse but not match any
            # real BW row → handler logs warning + returns.
            "bw_id": str(uuid4()),
        },
    )
    assert fire_resp.status == 200
    data = fire_resp.json()
    assert data["webhook_status"] == 200, data.get("webhook_body")


def test_webhook_checkout_subscription_invalid_bw_id_returns_200(
    page: Page, base_url: str
) -> None:
    """`checkout.session.completed` with `mode=subscription` and a
    non-UUID `bw_id` hits the `« invalid bw_id »` warning branch
    (UUID parse fails). Webhook still returns 200."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": "checkout.session.completed",
            "mode": "subscription",
            "bw_id": "not-a-valid-uuid-shape",
        },
    )
    assert fire_resp.status == 200
    data = fire_resp.json()
    assert data["webhook_status"] == 200, data.get("webhook_body")


def test_webhook_checkout_subscription_missing_bw_id_returns_200(
    page: Page, base_url: str
) -> None:
    """`checkout.session.completed` with `mode=subscription` and no
    `bw_id` hits the `« checkout.session.completed without bw_id »`
    warning branch. Webhook still returns 200."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": "checkout.session.completed",
            "mode": "subscription",
            # bw_id absent → handler logs and returns.
        },
    )
    assert fire_resp.status == 200
    data = fire_resp.json()
    assert data["webhook_status"] == 200, data.get("webhook_body")


def test_webhook_checkout_unknown_mode_returns_200(
    page: Page, base_url: str
) -> None:
    """`checkout.session.completed` with `mode=setup` (neither
    `payment` nor `subscription`) hits the
    `« unexpected mode »` warning branch. Webhook still returns
    200."""
    fire_resp = page.request.post(
        f"{base_url}/debug/stripe/fire-webhook",
        form={
            "synthetic": "1",
            "event_type": "checkout.session.completed",
            "mode": "setup",
            "bw_id": str(uuid4()),
        },
    )
    assert fire_resp.status == 200
    data = fire_resp.json()
    assert data["webhook_status"] == 200, data.get("webhook_body")
